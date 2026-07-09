"use client";

import { ChatWidget } from "../widget/ChatWidget";

export default function Home() {
  return (
    <main className="min-h-screen">
      <section className="mx-auto max-w-2xl px-6 py-20">
        <span className="inline-block rounded-full border border-neutral-300 dark:border-neutral-700 px-3 py-1 text-xs text-neutral-500">
          Phase 5 · Chat widget
        </span>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight">
          Voice AI Assistant
        </h1>
        <p className="mt-3 text-neutral-500 leading-relaxed">
          This is a demo host page. The floating chat widget in the corner talks
          to the FastAPI backend over WebSocket — click it, ask a question, and
          watch the answer stream in. Try a suggested question, toggle dark mode,
          or use the mic button.
        </p>

        <ul className="mt-6 space-y-2 text-sm text-neutral-600 dark:text-neutral-400">
          <li>• Streaming responses with markdown &amp; code highlighting</li>
          <li>• Suggested questions, conversation history, clear &amp; feedback</li>
          <li>• Voice input UI (full audio pipeline lands in Phase 7)</li>
          <li>• Light / dark / responsive — embeddable via one snippet (Phase 10)</li>
        </ul>

        <p className="mt-8 text-xs text-neutral-400">
          Backend expected at{" "}
          <code className="rounded bg-neutral-200 dark:bg-neutral-800 px-1.5 py-0.5">
            {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}
          </code>
          . Start it, then interact with the widget.
        </p>
      </section>

      <ChatWidget
        config={{ title: "Company Assistant", subtitle: "Ask me anything" }}
      />
    </main>
  );
}
