from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from channels.exceptions import DenyConnection
from langchain.schema import (
    SystemMessage,
    HumanMessage,
    AIMessage
)
from langchain.prompts import ChatPromptTemplate
from langchain.callbacks.base import BaseCallbackHandler

from langchain_ollama import ChatOllama

from langchain_milvus import Milvus
from langchain_ollama import OllamaEmbeddings

class WebsocketStreamingHandler(BaseCallbackHandler):
    """웹소켓을 통한 스트리밍 처리를 위한 콜백 핸들러"""

    def __init__(self, consumer, message_id):
        self.consumer = consumer
        self.message_id = message_id
        self.full_response = ""

    async def on_llm_new_token(self, token: str, **kwargs):
        """새로운 토큰이 생성될 때마다 호출"""
        self.full_response += token
        await self.consumer.send_json({
            'type': 'stream_chunk',
            'message_id': self.message_id,
            'content': token
        })

class ChatConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = 1
        self.conversation_id = None
        self.conversation = None

        self.uri = "http://localhost:19530"

        self.embeddings = OllamaEmbeddings(
            model="snowflake-arctic-embed2",
            base_url="http://localhost:11434"
        )

        self.vector_store = Milvus(
            embedding_function=self.embeddings,
            connection_args={"uri": self.uri},
        )

        self.retriever = self.vector_store.as_retriever()



    async def connect(self):
        try:
            self.conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")
            if not self.conversation_id:
                raise DenyConnection("Conversation ID is required")
            self.conversation = await self.get_conversation()
            await self.ensure_system_message()

            await self.accept()
            await self.send_json({
                'type': 'connection_established',
                'conversation_id': self.conversation_id
            })

        except DenyConnection as e:
            await self.close(code=4001)
        except Exception as e:
            await self.close(code=4000)

    async def disconnect(self, close_code):
        if hasattr(self, 'conversation_id'):
            await self.channel_layer.group_discard(
                f"chat_{self.conversation_id}",
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        try:
            message = content.get('message', '').strip()
            if not message:
                raise ValueError("Message content is required")

            # 사용자 메시지 저장
            user_message = await self.save_message(message, 'user')

            # 사용자 메시지 전송 확인
            await self.send_json({
                'type': 'message_received',
                'message_id': user_message.id,
                'content': message
            })

            messages = await self.get_conversation_context()
            # LLM 응답 처리
            response = await self.get_llm_response(message, messages, user_message.id)
            print(response)
            if response:  # response가 None이 아닌 경우에만 처리
                assistant_message = await self.save_message(
                    response,
                    'assistant',
                    parent_message_id=user_message.id
                )

                await self.send_json({
                    'type': 'stream_end',
                    'message_id': assistant_message.id,
                    'timestamp': assistant_message.created_at.isoformat()
                })

        except ValueError as e:
            await self.send_json({
                'type': 'error',
                'error_type': 'validation_error',
                'message': str(e)
            })
        except Exception as e:
            await self.send_json({
                'type': 'error',
                'error_type': 'system_error',
                'message': "An unexpected error occurred"
            })

    def format_docs(self, docs):
        return '\n\n'.join([d.page_content for d in docs])

    async def get_llm_response(self, user_message, context_messages, message_id):
        """LLM 응답 생성"""
        try:
            llm = ChatOllama(
                model="llama3.2-vision",
                temperature=0.8,
                num_predict=256,
                streaming=True
            )

            # 시스템 프롬프트 설정
            system_prompt = "You are an AI assistant. Always respond in Korean. Keep responses clear and concise."

            # 메시지 포맷팅
            formatted_messages = []
            for msg in context_messages:
                if msg["role"] == "system":
                    formatted_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    formatted_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    formatted_messages.append(AIMessage(content=msg["content"]))

            formatted_messages.append(HumanMessage(content=user_message))

            # 스트리밍 핸들러 설정
            stream_handler = WebsocketStreamingHandler(self, message_id)

            # 프롬프트 템플릿 설정
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("system", "Context information is below:\n{context}\n"),
                *[(msg.type, msg.content) for msg in formatted_messages]
            ])
            res = self.retriever.invoke(user_message)
            context = self.format_docs(res)
            print(context)
            # 체인 실행
            chain = prompt | llm.with_config({"callbacks": [stream_handler]})
            response = await chain.ainvoke({
                "input": user_message,
                "context": context
            })

            return stream_handler.full_response

        except Exception as e:
            error_msg = f"LLM API error: {str(e)}"
            await self.send_json({
                'type': 'error',
                'message': error_msg
            })
            return None

    @database_sync_to_async
    def get_conversation(self):
        """Get conversation with proper error handling"""
        from chat.models import Conversation
        try:
            conversation = Conversation.objects.get(
                id=self.conversation_id,
                user=self.user
            )
            return conversation
        except Conversation.DoesNotExist:
            raise DenyConnection("Conversation not found")
        except Exception as e:
            raise DenyConnection(f"Failed to get conversation: {str(e)}")

    @database_sync_to_async
    def save_message(self, content, role, parent_message_id=None):
        """Save message with proper validation"""
        from chat.models import Message

        if not content or not role:
            raise ValueError("Message content and role are required")

        try:
            message = Message.objects.create(
                conversation=self.conversation,
                role=role,
                content=content,
                parent_message_id=parent_message_id
            )
            return message
        except Exception as e:
            raise Exception(f"Failed to save message: {str(e)}")

    @database_sync_to_async
    def ensure_system_message(self):
        """시스템 메시지가 없는 경우 생성"""
        from chat.models import Message

        system_message = Message.objects.filter(
            conversation=self.conversation,
            role='system'
        ).first()
        if not system_message:
            Message.objects.create(
                conversation=self.conversation,
                role='system',
                content="You are llama, an AI assistant created by llama3.2-vision"
            )

    @database_sync_to_async
    def get_conversation_context(self):
        """Get conversation context with proper message ordering"""
        from .models import Message
        messages = []
        # First get system message
        system_message = Message.objects.filter(conversation=self.conversation, role='system').first()
        if system_message:
            messages.append({
                'role': 'system',
                'content': system_message.content
            })
        # Then get conversation history with proper ordering
        recent_messages = Message.objects.filter(conversation=self.conversation).exclude(role='system') \
            .order_by('created_at') \

        # Consider adding a limit to prevent context from growing too large
        for msg in recent_messages:
            messages.append({
                'role': msg.role,
                'content': msg.content
            })
        return messages
