"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { ChatMessage } from "@/lib/types";
import { sendChatMessage, getChatHistory } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

interface ChatPanelProps {
  onActionExecuted: () => void;
}

export default function ChatPanel({ onActionExecuted }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getChatHistory()
      .then(setMessages)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(text);
      setMessages((prev) => [...prev, response]);
      if (response.actions?.trades?.length || response.actions?.watchlist_changes?.length) {
        onActionExecuted();
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: err instanceof Error ? err.message : "Failed to get response",
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, onActionExecuted]);

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="fixed right-0 top-1/2 -translate-y-1/2 bg-accent-purple text-white text-xs px-1 py-6 rounded-l writing-mode-vertical hover:opacity-80 z-10"
        style={{ writingMode: "vertical-rl" }}
      >
        AI Chat
      </button>
    );
  }

  return (
    <div className="flex flex-col h-full border-l border-border bg-bg-card">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold text-accent-blue">AI Assistant</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-text-secondary hover:text-text-primary text-xs"
        >
          Collapse
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <p className="text-text-secondary text-xs text-center mt-4">
            Ask about your portfolio, request trades, or get analysis.
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`text-xs ${msg.role === "user" ? "text-right" : "text-left"}`}
          >
            <div
              className={`inline-block max-w-[90%] rounded px-3 py-2 ${
                msg.role === "user"
                  ? "bg-accent-purple/30 text-text-primary"
                  : "bg-bg-secondary text-text-primary"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.actions?.trades && msg.actions.trades.length > 0 && (
                <div className="mt-2 border-t border-border/50 pt-1.5 space-y-1">
                  {msg.actions.trades.map((t, i) => (
                    <div
                      key={i}
                      className={`text-[10px] ${
                        t.side === "buy" ? "text-profit" : "text-loss"
                      }`}
                    >
                      {t.side.toUpperCase()} {t.quantity} {t.ticker} @ {formatCurrency(t.price)}
                    </div>
                  ))}
                </div>
              )}
              {msg.actions?.watchlist_changes && msg.actions.watchlist_changes.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {msg.actions.watchlist_changes.map((w, i) => (
                    <div key={i} className="text-[10px] text-accent-yellow">
                      {w.action === "add" ? "+" : "-"} {w.ticker} watchlist
                    </div>
                  ))}
                </div>
              )}
              {msg.actions?.errors && msg.actions.errors.length > 0 && (
                <div className="mt-1 space-y-0.5">
                  {msg.actions.errors.map((e, i) => (
                    <div key={i} className="text-[10px] text-loss">
                      Error: {e}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="text-xs text-text-secondary animate-pulse">Thinking...</div>
        )}
      </div>

      <div className="p-2 border-t border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask the AI..."
            className="flex-1 bg-bg-primary border border-border rounded px-2 py-1.5 text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent-blue"
          />
          <button
            onClick={handleSend}
            disabled={loading}
            className="bg-accent-purple text-white text-xs px-3 py-1.5 rounded hover:opacity-80 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
