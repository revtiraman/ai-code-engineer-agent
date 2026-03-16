"use client";

import { useEffect, useRef } from "react";
import { RunStatus } from "./AIEngineerApp";

interface Props {
  logs:   string[];
  status: RunStatus;
}

function colorLine(line: string): string {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("fatal") || l.includes("❌"))
    return "log-line-error";
  if (l.includes("warn") || l.includes("⚠"))
    return "log-line-warning";
  if (l.includes("✅") || l.includes("success") || l.includes("passed") || l.includes("completed"))
    return "log-line-success";
  if (l.includes("agent running") || l.includes("step "))
    return "log-line-header";
  return "log-line-info";
}

export default function LogPanel({ logs, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // auto-scroll to bottom on new logs
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="flex flex-col h-full">

      {/* toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <span className="text-xs font-semibold text-muted uppercase tracking-widest">
          Live Logs
        </span>
        <span className="text-[10px] text-muted">{logs.length} lines</span>
      </div>

      {/* log output */}
      <div className="flex-1 overflow-y-auto p-4 text-[11px] leading-relaxed">

        {logs.length === 0 && status === "idle" && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-muted">
            <span className="text-4xl">🤖</span>
            <p className="text-xs">Set a repo URL and prompt, then click <strong className="text-accent">Run Pipeline</strong></p>
          </div>
        )}

        {logs.length === 0 && status === "running" && (
          <div className="flex items-center gap-2 text-muted">
            <span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-xs">Connecting…</span>
          </div>
        )}

        {logs.map((line, i) => (
          <div
            key={i}
            className={`font-mono whitespace-pre-wrap break-all ${colorLine(line)}`}
          >
            {line}
          </div>
        ))}

        {status === "running" && logs.length > 0 && (
          <div className="flex items-center gap-2 text-muted mt-1">
            <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

    </div>
  );
}
