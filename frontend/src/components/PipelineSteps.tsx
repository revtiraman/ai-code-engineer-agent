"use client";

import { RunStatus } from "./AIEngineerApp";

interface Props {
  activeStep: number;
  doneSteps:  Set<number>;
  status:     RunStatus;
}

const STEPS = [
  { label: "Load Repo",    icon: "📦" },
  { label: "Index",        icon: "🗂️" },
  { label: "Retrieve",     icon: "🔍" },
  { label: "Plan",         icon: "📋" },
  { label: "Edit",         icon: "✏️" },
  { label: "Validate",     icon: "🔎" },
  { label: "Execute",      icon: "⚙️" },
  { label: "Test",         icon: "🧪" },
  { label: "Commit",       icon: "💾" },
  { label: "Push",         icon: "🚀" },
  { label: "Pull Request", icon: "🔀" },
];

export default function PipelineSteps({ activeStep, doneSteps, status }: Props) {
  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-xs font-semibold text-muted uppercase tracking-widest mb-2">
        Pipeline Steps
      </h2>

      {STEPS.map((step, i) => {
        const isDone   = doneSteps.has(i);
        const isActive = activeStep === i;
        const isPending = !isDone && !isActive;

        return (
          <div
            key={i}
            className={`
              flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-all
              ${isDone   ? "text-success bg-success/10" : ""}
              ${isActive ? "text-white  bg-accent/15 border border-accent/30" : ""}
              ${isPending && activeStep === -1 ? "text-muted" : ""}
              ${isPending && activeStep > -1   ? "text-muted opacity-50" : ""}
            `}
          >
            {/* indicator */}
            <span className="w-5 text-center shrink-0">
              {isDone   && <span className="text-success">✓</span>}
              {isActive && (
                status === "running"
                  ? <span className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin inline-block" />
                  : <span className="text-accent">◆</span>
              )}
              {isPending && <span className="text-border text-[10px]">○</span>}
            </span>

            {/* step info */}
            <span className="text-base leading-none">{step.icon}</span>
            <span className="font-medium">{step.label}</span>

            {/* step number */}
            <span className="ml-auto text-[10px] text-muted font-normal">{i + 1}</span>
          </div>
        );
      })}

      {status === "completed" && (
        <div className="mt-3 px-2 py-2 rounded bg-success/10 border border-success/30 text-success text-xs font-semibold text-center">
          ✅ Pipeline completed
        </div>
      )}

      {status === "error" && (
        <div className="mt-3 px-2 py-2 rounded bg-error/10 border border-error/30 text-error text-xs font-semibold text-center">
          ❌ Pipeline error
        </div>
      )}
    </div>
  );
}
