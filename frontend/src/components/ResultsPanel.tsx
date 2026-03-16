"use client";

import { useState, useEffect } from "react";
import { RunResult } from "./AIEngineerApp";

interface Props {
  result:  RunResult;
  runId:   string | null;
  apiBase: string;
}

interface DiffData {
  stat:  string;
  patch: string;
}

type Tab = "files" | "tests" | "diff" | "pr";

export default function ResultsPanel({ result, runId, apiBase }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("files");
  const [diff,      setDiff]      = useState<DiffData | null>(null);
  const [loadingDiff, setLoadingDiff] = useState(false);

  const planMode =
    result.plan && typeof result.plan === "object"
      ? String((result.plan as Record<string, unknown>).mode ?? "")
      : "";
  const isExplainOnly = planMode === "explain_only";

  const tabs: { key: Tab; label: string; badge?: string }[] = [
    { key: "files", label: "Edited Files",    badge: String(result.edited_files?.length ?? 0) },
    { key: "tests", label: "Test Results",    badge: result.tests_passed ? "✓" : result.test_results ? "✗" : "—" },
    { key: "diff",  label: "Git Diff"  },
    { key: "pr",    label: "Pull Request", badge: result.pr_url ? "✓" : undefined },
  ];

  useEffect(() => {
    if (activeTab === "diff" && !diff && runId) {
      setLoadingDiff(true);
      fetch(`${apiBase}/api/diff/${runId}`)
        .then(r => r.json())
        .then(d => { setDiff(d); setLoadingDiff(false); })
        .catch(() => { setLoadingDiff(false); });
    }
  }, [activeTab, diff, runId, apiBase]);

  return (
    <div className="flex flex-col" style={{ maxHeight: "40vh" }}>

      {/* tab bar */}
      <div className="flex items-center gap-0 border-b border-border px-4 pt-2 shrink-0">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`
              flex items-center gap-1.5 px-3 py-1.5 text-xs border-b-2 transition-colors
              ${activeTab === tab.key
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-white"}
            `}
          >
            {tab.label}
            {tab.badge && (
              <span className={`
                px-1.5 py-0.5 rounded text-[10px] font-mono
                ${tab.badge === "✓" ? "bg-success/20 text-success" :
                  tab.badge === "✗" ? "bg-error/20 text-error" :
                  "bg-surface text-muted"}
              `}>
                {tab.badge}
              </span>
            )}
          </button>
        ))}

        <div className="ml-auto flex items-center gap-3 pb-1">
          {isExplainOnly ? (
            <span className="text-xs font-semibold text-success">📘 Explanation generated</span>
          ) : (
            <span className={`text-xs font-semibold ${result.execution_success ? "text-success" : "text-error"}`}>
              {result.execution_success ? "✅ Build passed" : "❌ Build failed"}
            </span>
          )}
        </div>
      </div>

      {/* tab content */}
      <div className="flex-1 overflow-y-auto p-4 text-xs">

        {/* ── Edited Files ── */}
        {activeTab === "files" && (
          <div className="flex flex-col gap-1">
            {result.explanation_file && (
              <div className="mb-3 border border-border rounded p-3 bg-surface">
                <p className="text-[10px] text-muted uppercase tracking-widest mb-1">Explanation File</p>
                <p className="text-white font-mono break-all">{result.explanation_file}</p>
                {result.explanation_preview && (
                  <pre className="mt-2 text-[10px] text-muted whitespace-pre-wrap overflow-x-auto max-h-28 overflow-y-auto">
                    {result.explanation_preview}
                  </pre>
                )}
              </div>
            )}
            {(result.edited_files ?? []).length === 0 ? (
              <span className="text-muted">No files were edited.</span>
            ) : (
              result.edited_files!.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-surface rounded border border-border">
                  <span className="text-warning">~</span>
                  <span className="text-white font-mono">{f}</span>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Test Results ── */}
        {activeTab === "tests" && (
          <div className="flex flex-col gap-2">
            {!result.test_results || Object.keys(result.test_results).length === 0 ? (
              <span className="text-muted">No test results available.</span>
            ) : (
              Object.entries(result.test_results).map(([file, r]) => (
                <div key={file} className="border border-border rounded p-3 bg-surface">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-semibold truncate">{file}</span>
                    <span className={`
                      text-[11px] px-2 py-0.5 rounded font-semibold
                      ${r.status === "passed"  ? "bg-success/20 text-success" :
                        r.status === "skipped" ? "bg-muted/20  text-muted"   :
                        r.status === "timeout" ? "bg-warning/20 text-warning" :
                                                 "bg-error/20   text-error"}
                    `}>
                      {r.status}
                    </span>
                  </div>
                  {r.output && (
                    <pre className="text-[10px] text-muted whitespace-pre-wrap overflow-x-auto max-h-24 overflow-y-auto">
                      {r.output}
                    </pre>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* ── Diff ── */}
        {activeTab === "diff" && (
          <div>
            {loadingDiff && (
              <div className="flex items-center gap-2 text-muted">
                <span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                Loading diff…
              </div>
            )}
            {!loadingDiff && diff && (
              <div className="flex flex-col gap-3">
                {diff.stat && (
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-widest mb-1">Stat</p>
                    <pre className="text-[11px] text-accent bg-surface p-2 rounded">{diff.stat}</pre>
                  </div>
                )}
                {diff.patch && (
                  <div>
                    <p className="text-[10px] text-muted uppercase tracking-widest mb-1">Diff</p>
                    <pre className="text-[10px] text-muted whitespace-pre overflow-x-auto bg-surface p-2 rounded max-h-48 overflow-y-auto leading-5">
                      {diff.patch.split("\n").map((line, i) => (
                        <span
                          key={i}
                          className={`block ${
                            line.startsWith("+")  ? "text-success" :
                            line.startsWith("-")  ? "text-error"   :
                            line.startsWith("@@") ? "text-warning"  :
                            ""
                          }`}
                        >
                          {line}
                        </span>
                      ))}
                    </pre>
                  </div>
                )}
              </div>
            )}
            {!loadingDiff && !diff && (
              <span className="text-muted">Click to load diff…</span>
            )}
          </div>
        )}

        {/* ── PR ── */}
        {activeTab === "pr" && (
          <div className="flex flex-col gap-3">
            {result.pr_url ? (
              <div className="flex flex-col gap-2">
                <p className="text-success font-semibold">Pull Request created ✅</p>
                <a
                  href={result.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="
                    inline-flex items-center gap-2 px-4 py-2 bg-accent/10
                    border border-accent/40 text-accent rounded
                    hover:bg-accent/20 transition-colors w-fit
                  "
                >
                  🔀 {result.pr_url}
                </a>
                {result.branch_name && (
                  <p className="text-muted text-[11px]">Branch: <code className="text-white">{result.branch_name}</code></p>
                )}
              </div>
            ) : (
              <span className="text-muted">
                {result.error
                  ? `Pipeline error: ${result.error}`
                  : "No pull request was created for this run."}
              </span>
            )}

            {result.debug_diagnosis && (
              <div className="mt-2">
                <p className="text-[10px] text-muted uppercase tracking-widest mb-1">Debugger Diagnosis</p>
                <pre className="text-[11px] text-warning bg-surface p-3 rounded whitespace-pre-wrap border border-warning/20">
                  {result.debug_diagnosis}
                </pre>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
