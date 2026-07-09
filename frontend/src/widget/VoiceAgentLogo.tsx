"use client";

import { cn } from "../lib/cn";

interface Props {
  className?: string;
}

/** Circular Voice Agent badge — concentric rings + ripple lines (launcher logo). */
export function VoiceAgentLogo({ className }: Props) {
  return (
    <div className={cn("va-logo", className)} aria-hidden>
      <span className="va-logo-ripple va-logo-ripple--1" />
      <span className="va-logo-ripple va-logo-ripple--2" />
      <span className="va-logo-ripple va-logo-ripple--3" />
      <span className="va-logo-ripple va-logo-ripple--4" />
      <div className="va-logo-disc">
        <span className="va-logo-line">Voice</span>
        <span className="va-logo-line">Agent</span>
      </div>
    </div>
  );
}
