"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Loader2, Plus, Send, User } from "lucide-react";
import { streamMessage } from "@/lib/api";
import type { ChatMessage } from "@/types";

// ── Quick prompts shown on the empty/welcome screen ──────────────────────────

const QUICK_PROMPTS = [
  { label: "Expiring leases",    prompt: "Show me leases expiring in the next 90 days" },
  { label: "Available units",    prompt: "Which units are currently available?" },
  { label: "RERA 90-day rule",   prompt: "What is the RERA 90-day notice rule?" },
  { label: "Open maintenance",   prompt: "Show all open maintenance requests" },
  { label: "Tenant documents",   prompt: "What documents does a tenant need to sign a lease?" },
  { label: "Ejari registration", prompt: "How do I register a lease with Ejari?" },
];

// ── Thread ID helpers ─────────────────────────────────────────────────────────

function newThreadId() {
  return `thread-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getOrCreateThreadId(): string {
  if (typeof window === "undefined") return newThreadId();
  const stored = localStorage.getItem("lma_thread_id");
  if (stored) return stored;
  const id = newThreadId();
  localStorage.setItem("lma_thread_id", id);
  return id;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex items-start gap-3 flex-row-reverse">
      <div className="shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white">
        <User size={15} />
      </div>
      <div className="max-w-[78%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="shrink-0 w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center text-white">
        <Bot size={15} />
      </div>
      <div className="max-w-[78%] bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-sm">
        {content}
      </div>
    </div>
  );
}

function StreamingBubble({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="shrink-0 w-8 h-8 rounded-full bg-slate-900 flex items-center justify-center text-white">
        <Bot size={15} />
      </div>
      <div className="max-w-[78%] bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-sm">
        {text || <Loader2 size={14} className="animate-spin text-slate-400" />}
        {text && (
          <span className="inline-block w-0.5 h-[1em] bg-slate-400 animate-pulse ml-0.5 align-text-bottom" />
        )}
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") return <UserBubble content={msg.content} />;
  return <AssistantBubble content={msg.content} />;
}

// ── Main component ────────────────────────────────────────────────────────────

export function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamBuffer, setStreamBuffer] = useState("");

  const threadId = useRef(getOrCreateThreadId());
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamBuffer, scrollToBottom]);

  // ── New chat ────────────────────────────────────────────────────────────────

  function resetChat() {
    abortRef.current?.abort();
    const id = newThreadId();
    localStorage.setItem("lma_thread_id", id);
    threadId.current = id;
    setMessages([]);
    setStreamBuffer("");
    setStreaming(false);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  // ── Send message ────────────────────────────────────────────────────────────

  async function submit(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setStreamBuffer("");

    const controller = new AbortController();
    abortRef.current = controller;
    let fullText = "";

    try {
      await streamMessage(
        trimmed,
        threadId.current,
        (chunk) => {
          fullText += chunk;
          setStreamBuffer(fullText);
        },
        () => {
          setMessages((prev) => [
            ...prev,
            {
              id: `a-${Date.now()}`,
              role: "assistant",
              content: fullText || "(no response)",
              timestamp: new Date(),
            },
          ]);
          setStreamBuffer("");
          setStreaming(false);
          setTimeout(() => inputRef.current?.focus(), 0);
        },
        (err) => {
          setMessages((prev) => [
            ...prev,
            {
              id: `err-${Date.now()}`,
              role: "assistant",
              content: `Something went wrong: ${err}`,
              timestamp: new Date(),
            },
          ]);
          setStreamBuffer("");
          setStreaming(false);
        },
        controller.signal
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content: "Could not connect to the backend. Make sure the FastAPI server is running on port 8000.",
          timestamp: new Date(),
        },
      ]);
      setStreamBuffer("");
      setStreaming(false);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  const isEmpty = messages.length === 0 && !streaming;

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-slate-50">

      {/* ── Top bar ── */}
      <div className="shrink-0 flex items-center justify-between px-5 py-3 bg-white border-b border-slate-200">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-slate-900 flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <div className="leading-none">
            <p className="text-sm font-semibold text-slate-900">Lease Manager AI</p>
            <p className="text-[11px] text-slate-400 mt-0.5">GPT-4o · RERA-aware</p>
          </div>
        </div>

        <button
          onClick={resetChat}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600 border border-slate-200 rounded-lg bg-white hover:bg-slate-50 transition-colors"
        >
          <Plus size={13} />
          New chat
        </button>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (

          /* Welcome screen */
          <div className="flex flex-col items-center justify-center h-full px-6 pb-12">
            <div className="w-16 h-16 rounded-2xl bg-slate-900 flex items-center justify-center mb-5 shadow-lg">
              <Bot size={28} className="text-white" />
            </div>
            <h2 className="text-2xl font-bold text-slate-900 mb-2">How can I help?</h2>
            <p className="text-sm text-slate-500 mb-8 text-center max-w-sm">
              Ask about leases, tenants, available units, maintenance, or Dubai real estate law.
            </p>
            <div className="grid grid-cols-2 gap-2.5 w-full max-w-lg">
              {QUICK_PROMPTS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => submit(p.prompt)}
                  className="text-left px-4 py-3 rounded-xl bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50/40 transition-all shadow-sm"
                >
                  <p className="text-xs font-semibold text-slate-800">{p.label}</p>
                  <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{p.prompt}</p>
                </button>
              ))}
            </div>
          </div>

        ) : (

          /* Conversation */
          <div className="max-w-3xl mx-auto w-full px-6 py-6 space-y-5">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {streaming && <StreamingBubble text={streamBuffer} />}
            <div ref={bottomRef} />
          </div>

        )}
      </div>

      {/* ── Input bar ── */}
      <div className="shrink-0 bg-white border-t border-slate-200 px-6 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-3 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus-within:ring-2 focus-within:ring-blue-500/30 focus-within:border-blue-300 transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message Lease Manager AI…"
              rows={1}
              disabled={streaming}
              className="flex-1 resize-none bg-transparent text-sm text-slate-800 placeholder-slate-400 focus:outline-none disabled:opacity-60 max-h-36"
              style={{ fieldSizing: "content" } as React.CSSProperties}
            />
            <button
              onClick={() => submit(input)}
              disabled={streaming || !input.trim()}
              className="shrink-0 w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center hover:bg-slate-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label={streaming ? "Generating…" : "Send"}
            >
              {streaming
                ? <Loader2 size={14} className="animate-spin" />
                : <Send size={14} />
              }
            </button>
          </div>
          <p className="text-[11px] text-slate-400 mt-2 text-center">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>

    </div>
  );
}
