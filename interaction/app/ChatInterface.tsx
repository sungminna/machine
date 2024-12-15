'use client'
import React, { useState, useRef, useEffect } from 'react';
import { Send } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";

// 두 문자열 간의 중복되는 부분 찾기
const findOverlap = (str1: string, str2: string) => {
  const minLength = Math.min(str1.length, str2.length);
  for (let i = minLength; i > 0; i--) {
    const end = str1.slice(-i);
    const start = str2.slice(0, i);
    if (end === start) {
      return i;
    }
  }
  return 0;
};

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: '안녕하세요! 무엇을 도와드릴까요?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const conversationId = '1';
    const ws = new WebSocket(`ws://localhost:8000/api/ws/chat/conversations/${conversationId}/`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'stream_chunk') {
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMessage = newMessages[newMessages.length - 1];
          
          const lastContent = lastMessage.content;
          const newContent = data.content;
          
          if (lastContent) {
            const overlap = findOverlap(lastContent, newContent);
            if (overlap > 0) {
              lastMessage.content = lastContent + newContent.slice(overlap);
            } else {
              lastMessage.content = lastContent + newContent;
            }
          } else {
            lastMessage.content = newContent;
          }
          
          return newMessages;
        });
      } else if (data.type === 'stream_end') {
        setIsLoading(false);
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const scrollToBottom = () => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        const scrollHeight = scrollContainer.scrollHeight;
        scrollContainer.style.scrollBehavior = 'smooth';
        scrollContainer.scrollTop = scrollHeight;
      }
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || !wsRef.current) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage, { role: 'assistant', content: '' }]);
    setInput('');
    setIsLoading(true);
    
    wsRef.current.send(JSON.stringify({
      message: input
    }));
  };

  return (
    <div className="h-screen p-8 md:p-16">
      <div className="flex flex-col h-full max-w-6xl mx-auto">
        <Card className="flex-1 mb-6">
          <ScrollArea 
            ref={scrollAreaRef} 
            className="h-[calc(100vh-180px)] transition-all duration-300 ease-in-out"
          >
            <div className="p-6">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`mb-6 ${
                    message.role === 'user' 
                      ? 'text-right' 
                      : 'text-left'
                  }`}
                >
                  <div
                    className={`inline-block rounded-lg px-6 py-3 max-w-[80%] whitespace-pre-wrap ${
                      message.role === 'user'
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        </Card>
        
        <form onSubmit={handleSubmit} className="flex gap-4">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="메시지를 입력하세요..."
            disabled={isLoading}
            className="flex-grow"
          />
          <Button type="submit" disabled={isLoading} size="lg">
            <Send className="h-5 w-5" />
          </Button>
        </form>
      </div>
    </div>
  );
}