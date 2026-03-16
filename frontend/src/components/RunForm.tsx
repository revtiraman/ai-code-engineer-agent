"use client";

import { useState, FormEvent } from "react";

interface Props {
  onRun:    (repoUrl: string, prompt: string) => void;
  disabled: boolean;
}

export default function RunForm({ onRun, disabled }: Props) {
  const [repoUrl, setRepoUrl] = useState("https://github.com/revtiraman/fastapi");
  const [prompt,  setPrompt]  = useState("Add logging to API routes");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (repoUrl.trim() && prompt.trim()) {
      onRun(repoUrl.trim(), prompt.trim());
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold text-muted uppercase tracking-widest mb-1">
        Configuration
      </h2>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted">Repository URL</span>
        <input
          type="text"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
          disabled={disabled}
          placeholder="https://github.com/user/repo"
          className="
            bg-surface border border-border rounded px-3 py-2 text-xs text-white
            placeholder:text-muted focus:outline-none focus:border-accent
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-xs text-muted">Task / Prompt</span>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          disabled={disabled}
          rows={3}
          placeholder="e.g. Add logging to API routes"
          className="
            bg-surface border border-border rounded px-3 py-2 text-xs text-white
            placeholder:text-muted focus:outline-none focus:border-accent resize-none
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        />
      </label>

      <button
        type="submit"
        disabled={disabled}
        className="
          flex items-center justify-center gap-2 bg-accent text-bg font-semibold
          text-xs py-2 px-4 rounded hover:bg-blue-400 active:scale-95
          transition-all disabled:opacity-50 disabled:cursor-not-allowed
          disabled:hover:bg-accent disabled:active:scale-100
        "
      >
        {disabled ? (
          <>
            <span className="w-3 h-3 border-2 border-bg border-t-transparent rounded-full animate-spin" />
            Running…
          </>
        ) : (
          <>▶ Run Pipeline</>
        )}
      </button>
    </form>
  );
}
