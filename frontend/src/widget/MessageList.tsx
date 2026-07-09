"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "../lib/cn";
import type { ChatMessageT } from "../lib/types";
import { Markdown } from "./Markdown";
import { TypingIndicator } from "./TypingIndicator";

interface Props {
  messages: ChatMessageT[];
  onFeedback: (message: ChatMessageT, rating: "up" | "down") => void;
}

export function MessageList({ messages, onFeedback }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the latest content as it streams in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} onFeedback={onFeedback} />
      ))}
      <div ref={endRef} />
    </div>
  );
}

function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessageT;
  onFeedback: (m: ChatMessageT, r: "up" | "down") => void;
}) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const showTyping = message.streaming && message.content.length === 0;

  if (isSystem) {
    return (
      <div className="text-center text-xs text-neutral-500 py-1">
        {message.content}
      </div>
    );
  }

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
          isUser
            ? "text-white rounded-br-sm"
            : "bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 rounded-bl-sm",
        )}
        style={isUser ? { backgroundColor: "var(--va-accent)" } : undefined}
      >
        {showTyping ? (
          <TypingIndicator />
        ) : isUser ? (
          <span className="whitespace-pre-wrap break-words">{message.content}</span>
        ) : (
          <>
            <Markdown content={message.content} />
            {message.streaming && <span className="va-caret" />}
          </>
        )}

        {!isUser && !message.streaming && message.content.length > 0 && (
          <BubbleFooter message={message} onFeedback={onFeedback} />
        )}
      </div>
    </div>
  );
}

function BubbleFooter({
  message,
  onFeedback,
}: {
  message: ChatMessageT;
  onFeedback: (m: ChatMessageT, r: "up" | "down") => void;
}) {
  const [rated, setRated] = useState<"up" | "down" | null>(null);
  const rate = (r: "up" | "down") => {
    if (rated || !message.serverId) return;
    setRated(r);
    onFeedback(message, r);
  };
  return (
    <div className="mt-1.5 flex items-center gap-2 text-neutral-400">
      {message.sources && message.sources.length > 0 && (
        <span className="text-[11px]">
          {message.sources.length} source
          {message.sources.length > 1 ? "s" : ""}
        </span>
      )}
      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          aria-label="Helpful"
          disabled={!message.serverId}
          onClick={() => rate("up")}
          className={cn(
            "px-1 rounded hover:text-green-500 transition-colors",
            rated === "up" && "text-green-500",
          )}
        >
          ▲
        </button>
        <button
          type="button"
          aria-label="Not helpful"
          disabled={!message.serverId}
          onClick={() => rate("down")}
          className={cn(
            "px-1 rounded hover:text-red-500 transition-colors",
            rated === "down" && "text-red-500",
          )}
        >
          ▼
        </button>
      </div>
    </div>
  );
}
