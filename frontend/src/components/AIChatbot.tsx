"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { usePathname } from "next/navigation";
import { useWatchlist } from "@/context/WatchlistContext";
import { getStarterQuestions } from "@/lib/ai/starterQuestions";

interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  isError?: boolean;
}

/**
 * Lightweight helper to render formatted text (bold, inline code, bullets, paragraphs).
 */
function FormattedMessageText({ text }: { text: string }) {
  const paragraphs = text.split("\n\n").filter(Boolean);

  return (
    <div className="space-y-2 text-xs leading-relaxed">
      {paragraphs.map((para, pIdx) => {
        const lines = para.split("\n").filter(Boolean);
        const isBulletList = lines.every((l) => l.trim().startsWith("- ") || l.trim().startsWith("* ") || /^\d+\.\s/.test(l.trim()));

        if (isBulletList) {
          return (
            <ul key={pIdx} className="space-y-1 list-disc pl-4 text-slate-300 dark:text-slate-300">
              {lines.map((line, lIdx) => {
                const cleanLine = line.replace(/^[-*]\s+|\d+\.\s+/, "");
                return (
                  <li key={lIdx} className="text-xs">
                    <InlineText text={cleanLine} />
                  </li>
                );
              })}
            </ul>
          );
        }

        return (
          <p key={pIdx}>
            {lines.map((line, lIdx) => (
              <React.Fragment key={lIdx}>
                {lIdx > 0 && <br />}
                <InlineText text={line} />
              </React.Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function InlineText({ text }: { text: string }) {
  // Parse bold **text** and inline `code`
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);

  return (
    <>
      {parts.map((part, idx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={idx} className="font-semibold text-white dark:text-white">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={idx}
              className="px-1 py-0.5 rounded bg-dark-bg border border-dark-border text-brand-300 text-[11px] font-mono"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={idx}>{part}</span>;
      })}
    </>
  );
}

export default function AIChatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { watchlist } = useWatchlist();

  const pathname = usePathname() || "/";
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // Extract symbol if on /companies/[symbol]
  const currentSymbol = useMemo(() => {
    if (pathname.startsWith("/companies/")) {
      const parts = pathname.split("/").filter(Boolean);
      return parts[1] ? parts[1].toUpperCase() : undefined;
    }
    return undefined;
  }, [pathname]);

  const pageAssistant = useMemo(
    () => getStarterQuestions(pathname, { symbol: currentSymbol, watchlistCount: watchlist.length }),
    [pathname, currentSymbol, watchlist.length]
  );
  const pageContextLabel = pageAssistant.label;

  // Scroll to bottom when messages update
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const handleSendMessage = async (textToSend?: string) => {
    const promptText = (textToSend || input).trim();
    if (!promptText || isLoading) return;

    const userMessageId = "msg-" + Date.now();
    const newMsg: Message = {
      id: userMessageId,
      role: "user",
      text: promptText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, newMsg]);
    setInput("");
    setIsLoading(true);

    try {
      // Build history payload for multi-turn context
      const historyPayload = messages.map((m) => ({
        role: m.role,
        text: m.text,
      }));

      const controller = new AbortController();
      const timeoutId = window.setTimeout(() => controller.abort(), 30_000);
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          message: promptText,
          route: pathname,
          symbol: currentSymbol,
          watchlist: pathname === "/watchlist" ? watchlist : undefined,
          history: historyPayload,
        }),
      }).finally(() => window.clearTimeout(timeoutId));

      const data = await res.json().catch(() => null) as { error?: string; reply?: string } | null;

      if (!res.ok) {
        throw new Error(data?.error || "Ask AI is temporarily unavailable. Please try again.");
      }
      if (!data?.reply?.trim()) throw new Error("Ask AI returned an empty response. Please try again.");

      const assistantMsg: Message = {
        id: "msg-asst-" + Date.now(),
        role: "assistant",
        text: data.reply.trim(),
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const errMsg = err instanceof DOMException && err.name === "AbortError"
        ? "Ask AI took too long to respond. Please try again."
        : err instanceof Error
          ? err.message
          : "Ask AI is temporarily unavailable. Please try again.";
      setMessages((prev) => [
        ...prev,
        {
          id: "msg-err-" + Date.now(),
          role: "assistant",
          text: `⚠️ ${errMsg}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearChat = () => {
    setMessages([]);
    inputRef.current?.focus();
  };

  return (
    <div className="fixed z-50 bottom-20 right-4 sm:bottom-6 sm:right-6 select-none font-sans">
      {/* Floating Action Button */}
      {!isOpen && (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          aria-label="Open PSE Forecast AI Assistant"
          className="group relative flex items-center gap-2.5 px-4 py-3 bg-gradient-to-r from-brand-600 to-blue-600 hover:from-brand-500 hover:to-blue-500 text-white font-semibold text-sm rounded-full shadow-lg hover:shadow-brand-500/25 transition-all duration-200 cursor-pointer active:scale-95 border border-brand-400/30 outline-none focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:ring-offset-2 focus-visible:ring-offset-dark-bg"
        >
          {/* Sparkle Icon */}
          <svg
            className="w-5 h-5 text-amber-300 animate-pulse"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
          </svg>
          <span>Ask AI</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping absolute -top-0.5 -right-0.5" />
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="PSE Forecast Assistant Chat"
          className="w-[calc(100vw-2rem)] sm:w-[420px] max-h-[85vh] sm:h-[580px] bg-dark-card border border-dark-border rounded-2xl shadow-2xl flex flex-col overflow-hidden backdrop-blur-xl transition-all duration-200 animate-in fade-in slide-in-from-bottom-5"
        >
          {/* Header */}
          <div className="px-4 py-3.5 bg-dark-bg/90 border-b border-dark-border flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-xl bg-brand-500/20 border border-brand-500/40 flex items-center justify-center shrink-0">
                <svg className="w-4 h-4 text-brand-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-white truncate">
                  PSE Pulse Ask AI
                </h3>
                <p className="text-[10px] text-slate-400 truncate">
                  Educational AI &middot; {pageContextLabel}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={clearChat}
                  title="Clear conversation"
                  aria-label="Clear chat"
                  className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-dark-bg rounded-lg transition-colors cursor-pointer text-xs outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                </button>
              )}
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Close chat (Esc)"
                aria-label="Close chat"
                className="p-1.5 text-slate-400 hover:text-white hover:bg-dark-bg rounded-lg transition-colors cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Context Banner */}
          <div className="px-3.5 py-1.5 bg-brand-500/10 border-b border-brand-500/20 text-[11px] flex items-center justify-between text-brand-300">
            <span className="font-medium truncate">{pageContextLabel}</span>
            <span className="text-[10px] text-slate-400 ml-2 shrink-0">Educational Only</span>
          </div>

          {/* Messages Area */}
          <div
            className="flex-1 p-4 overflow-y-auto space-y-3.5 select-text"
            role="log"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {messages.length === 0 ? (
              <div className="space-y-4 pt-2">
                <div className="text-center space-y-1">
                  <div className="w-10 h-10 mx-auto rounded-full bg-brand-500/10 border border-brand-500/30 flex items-center justify-center">
                    <svg className="w-5 h-5 text-brand-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                  </div>
                  <h4 className="text-xs font-semibold text-white">How can I assist you?</h4>
                  <p className="text-[11px] text-slate-400 max-w-[280px] mx-auto">
                    {pageAssistant.description}
                  </p>
                </div>

                {/* Starter Questions */}
                <div className="space-y-1.5 pt-1">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider px-1">
                    Starter Questions
                  </p>
                  <div className="space-y-1.5">
                    {pageAssistant.questions.map((q, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSendMessage(q)}
                        className="w-full text-left px-3 py-2 rounded-xl bg-dark-bg/80 hover:bg-dark-bg border border-dark-border/80 hover:border-brand-500/40 text-xs text-slate-200 hover:text-white transition-all cursor-pointer flex items-center justify-between group outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
                      >
                        <span className="min-w-0 whitespace-normal break-words">{q}</span>
                        <svg
                          className="w-3.5 h-3.5 text-slate-500 group-hover:text-brand-400 shrink-0 ml-2 transition-colors"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                >
                  <div
                    role={msg.isError ? "alert" : undefined}
                    className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-xs shadow-sm ${
                      msg.role === "user"
                        ? "bg-brand-600 text-white rounded-br-xs"
                        : msg.isError
                        ? "bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-bl-xs"
                        : "bg-dark-bg border border-dark-border text-slate-200 rounded-bl-xs"
                    }`}
                  >
                    {msg.role === "user" ? (
                      <p className="whitespace-pre-wrap">{msg.text}</p>
                    ) : (
                      <FormattedMessageText text={msg.text} />
                    )}
                  </div>
                  <span className="text-[9px] text-slate-500 mt-1 px-1">{msg.timestamp}</span>
                </div>
              ))
            )}

            {/* Loading typing bubble */}
            {isLoading && (
              <div className="flex flex-col items-start" role="status" aria-label="Ask AI is preparing a response">
                <div className="bg-dark-bg border border-dark-border rounded-2xl rounded-bl-xs px-4 py-3 flex items-center gap-1.5 shadow-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce [animation-delay:-0.3s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce [animation-delay:-0.15s]" />
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" />
                  <span className="text-[11px] text-slate-400 ml-1.5 font-medium">Analyzing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-dark-bg/90 border-t border-dark-border space-y-2">
            <div className="relative flex items-end gap-1.5 bg-dark-card border border-dark-border rounded-xl p-1.5 focus-within:ring-1 focus-within:ring-brand-500 focus-within:border-brand-500 transition-all">
              <textarea
                ref={inputRef}
                value={input}
                maxLength={1000}
                rows={1}
                disabled={isLoading}
                aria-label="Ask PSE Pulse AI a question"
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={isLoading ? "Waiting for response..." : "Ask a question about PSE forecasts..."}
                className="flex-1 max-h-24 resize-none bg-transparent px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none disabled:opacity-50"
              />

              <button
                type="button"
                onClick={() => handleSendMessage()}
                disabled={isLoading || !input.trim()}
                aria-label="Send question"
                className="p-1.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:hover:bg-brand-600 text-white rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              </button>
            </div>

            <div className="flex items-center justify-between text-[10px] text-slate-500 px-1">
              <span>Shift + Enter for new line</span>
              <span>{input.length}/1000</span>
            </div>
            <p className="text-[10px] leading-relaxed text-slate-500 px-1">
              PSE Pulse AI explains model outputs for educational purposes and does not provide investment advice.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
