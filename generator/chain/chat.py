import asyncio
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama


async def test():
    llm = ChatOllama(
        model="llama3.2-vision",
        temperature=0.8,
        num_predict=256,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "you are {language}. Response with {language}.",
            ),
            ("human", "{input}"),
        ]
    )
    messages = "introduce yourself"

    chain = prompt | llm

    async for chunk in chain.astream({
        "language": "Korean",
        "input": messages,
    }):
        print(chunk.content, end='')

if __name__ == '__main__':
    asyncio.run(test())