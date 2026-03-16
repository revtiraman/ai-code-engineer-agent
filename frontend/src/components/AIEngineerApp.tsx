"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import RunForm from "./RunForm";
import PipelineSteps from "./PipelineSteps";
import LogPanel from "./LogPanel";
import ResultsPanel from "./ResultsPanel";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS  = API.replace("http", "ws");

export type RunStatus = "idle" | "running" | "completed" | "error";

export interface TestResult {
  status: string;
  output: string;
}

export interface RunResult {
  edited_files?: string[];
  execution_success?: boolean;
  execution_error?: string;
  debug_diagnosis?: string;
  test_results?: Record<string, TestResult>;
  tests_passed?: boolean;
  pr_url?: string;
  branch_name?: string;
  plan?: Record<string, unknown>;
  explanation_file?: string;
  explanation_preview?: string;
  error?: string;
}

// Map log message fragments → step index
const STEP_TRIGGERS: [string, number][] = [
  ["Loading repository",     0],
  ["Step 1",                 0],
  ["Indexing repository",    1],
  ["Step 2",                 1],
  ["Searching repository",   2],
  ["retriever",              2],
  ["Planner Agent",          3],
  ["planner",                3],
  ["Editor Agent",           4],
  ["editor",                 4],
  ["Validator Agent",        5],
  ["validator",              5],
  ["Executor Agent",         6],
  ["executor",               6],
  ["Tester Agent",           7],
  ["tester",                 7],
  ["Commit Agent",           8],
  ["commit",                 8],
  ["Push Agent",             9],
  ["push",                   9],
  ["PR Agent",               10],
  ["pr_agent",               10],
];

function detectStep(line: string): number | null {
  const lower = line.toLowerCase();
  for (const [trigger, step] of STEP_TRIGGERS) {
    if (lower.includes(trigger.toLowerCase())) return step;
  }
  return null;
}

export default function AIEngineerApp() {
  const [status,      setStatus]      = useState<RunStatus>("idle");
  const [logs,        setLogs]        = useState<string[]>([]);
  const [activeStep,  setActiveStep]  = useState<number>(-1);
  const [doneSteps,   setDoneSteps]   = useState<Set<number>>(new Set());
  const [result,      setResult]      = useState<RunResult | null>(null);
  const [runId,       setRunId]       = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);

  const appendLog = useCallback((line: string) => {
    setLogs(prev => [...prev, line]);

    const step = detectStep(line);
    if (step !== null) {
      setActiveStep(curr => {
        if (step > curr) {
          // mark previous step as done
          setDoneSteps(prev => new Set([...prev, curr]));
          return step;
        }
        return curr;
      });
    }
  }, []);

  const handleRun = useCallback(async (repoUrl: string, prompt: string) => {
    // reset state
    setLogs([]);
    setResult(null);
    setActiveStep(-1);
    setDoneSteps(new Set());
    setStatus("running");

    try {
      const res = await fetch(`${API}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl, user_prompt: prompt }),
      });

      const { run_id } = await res.json();
      setRunId(run_id);

      // open WebSocket
      const ws = new WebSocket(`${WS}/api/ws/${run_id}`);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === "log") {
          appendLog(msg.message);
        } else if (msg.type === "done") {
          setStatus(msg.status === "completed" ? "completed" : "error");
          setResult(msg.result ?? null);
          setDoneSteps(prev => new Set([...prev, activeStep]));
          ws.close();
        }
        // ignore "ping"
      };

      ws.onerror = () => {
        appendLog("WebSocket error — check that the backend is running.");
        setStatus("error");
      };

    } catch (err) {
      appendLog(`Failed to start pipeline: ${err}`);
      setStatus("error");
    }
  }, [appendLog, activeStep]);

  // clean up on unmount
  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return (
    <div className="min-h-screen bg-bg flex flex-col font-mono">

      {/* ── Header ── */}
      <header className="border-b border-border px-6 py-4 flex items-center gap-3">
        <span className="text-2xl">🤖</span>
        <div>
          <h1 className="text-lg font-semibold text-white leading-tight">AI Engineer</h1>
          <p className="text-xs text-muted">Autonomous code modification pipeline</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {status === "running" && (
            <span className="flex items-center gap-2 text-xs text-warning">
              <span className="w-2 h-2 rounded-full bg-warning animate-pulse" />
              Running
            </span>
          )}
          {status === "completed" && (
            <span className="flex items-center gap-2 text-xs text-success">
              <span className="w-2 h-2 rounded-full bg-success" />
              Completed
            </span>
          )}
          {status === "error" && (
            <span className="flex items-center gap-2 text-xs text-error">
              <span className="w-2 h-2 rounded-full bg-error" />
              Error
            </span>
          )}
        </div>
      </header>

      {/* ── Main layout ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left column */}
        <aside className="w-80 border-r border-border flex flex-col overflow-y-auto shrink-0">
          <div className="p-4">
            <RunForm onRun={handleRun} disabled={status === "running"} />
          </div>
          <div className="border-t border-border p-4 flex-1">
            <PipelineSteps activeStep={activeStep} doneSteps={doneSteps} status={status} />
          </div>
        </aside>

        {/* Right: logs */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <LogPanel logs={logs} status={status} />
        </main>

      </div>

      {/* ── Results ── */}
      {result && (
        <div className="border-t border-border">
          <ResultsPanel result={result} runId={runId} apiBase={API} />
        </div>
      )}

    </div>
  );
}
