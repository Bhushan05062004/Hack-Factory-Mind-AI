import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  usage?: { input_tokens: number; output_tokens: number; llm_used: boolean };
  timestamp: Date;
}

export default function Chat() {
  const { api, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  let msgId = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { id: ++msgId.current, role: 'user', text, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/chat', { message: text });
      const data = res.data;
      const assistantMsg: Message = {
        id: ++msgId.current,
        role: 'assistant',
        text: data.message || data.fallback || 'No response.',
        usage: data.usage,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errMsg: Message = {
        id: ++msgId.current,
        role: 'assistant',
        text: `⚠️ Error: ${err.response?.data?.detail || err.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const suggestions = user?.role === 'user'
    ? ['I need 200 titanium flanges with 80mm bore, deliver by 2025-07-20', 'Show me all my orders', 'Do you have steel brackets?', 'Cancel order #1']
    : user?.role === 'operator'
    ? ['Move order #1 to In Review', 'Accept order #1', 'Show all received orders', 'What is the inspection procedure for flanges?']
    : ['Quality update on order #1 — passed visual inspection', 'Show all orders', 'What is the weld quality assessment process?'];

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12 animate-fade-in">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 border border-indigo-500/20 mb-4">
              <svg className="w-7 h-7 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
            </div>
            <h3 className="text-white/80 font-semibold mb-1">Start a conversation</h3>
            <p className="text-white/30 text-sm mb-6">Try one of these suggestions:</p>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto">
              {suggestions.map((s, i) => (
                <button key={i} onClick={() => { setInput(s); inputRef.current?.focus(); }}
                  className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white/50 text-xs hover:bg-white/10 hover:text-white/80 transition-all">
                  {s.length > 50 ? s.slice(0, 50) + '...' : s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} message-animate`}>
            <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-gradient-to-r from-indigo-500 to-violet-600 text-white rounded-br-md'
                : 'glass-card text-white/90 rounded-bl-md'
            }`}>
              <div className="whitespace-pre-wrap">{msg.text}</div>
              {msg.usage && msg.usage.llm_used && (
                <div className="mt-2 pt-2 border-t border-white/10 text-[10px] text-white/30 flex gap-3">
                  <span>In: {msg.usage.input_tokens}</span>
                  <span>Out: {msg.usage.output_tokens}</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start message-animate">
            <div className="glass-card px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex gap-1.5">
                <div className="w-2 h-2 bg-indigo-400 rounded-full typing-dot" />
                <div className="w-2 h-2 bg-indigo-400 rounded-full typing-dot" />
                <div className="w-2 h-2 bg-indigo-400 rounded-full typing-dot" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t border-white/5">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            ref={inputRef}
            id="chat-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Type your message..."
            className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-white/30 outline-none input-glow transition-all text-sm"
            disabled={loading}
          />
          <button
            id="chat-send"
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-5 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white font-medium rounded-xl hover:shadow-lg hover:shadow-indigo-500/25 transition-all disabled:opacity-50 text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
