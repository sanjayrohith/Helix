import { useEffect, useRef, useState } from 'react';
import { INTENT_TEMPLATES } from '../data/intentTemplates';
import type { IntentHistoryEntry } from '../hooks/useIntentHistory';

interface IntentInputProps {
  onSubmit: (intent: string) => void;
  onSimulate: (intent: string) => void;
  loading: boolean;
  simulating: boolean;
  history: IntentHistoryEntry[];
  onClearHistory: () => void;
  parserLabel?: string;
}

const PLACEHOLDER = `Describe your network slice requirement in plain English...

Example: "Create a high-security low-latency slice for 500 hospital devices in Chennai with guaranteed 50Mbps"`;

export function IntentInput({
  onSubmit,
  onSimulate,
  loading,
  simulating,
  history,
  onClearHistory,
  parserLabel,
}: IntentInputProps) {
  const [intent, setIntent] = useState('');
  const [panel, setPanel] = useState<'templates' | 'history' | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const busy = loading || simulating;
  const trimmed = intent.trim();

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (trimmed && !busy) onSubmit(trimmed);
  };

  // Ctrl/Cmd+Enter provisions, Ctrl/Cmd+Shift+Enter dry-runs: both are faster
  // than reaching for the mouse when iterating on wording.
  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      if (!trimmed || busy) return;
      if (event.shiftKey) onSimulate(trimmed);
      else onSubmit(trimmed);
    }
  };

  const apply = (value: string) => {
    setIntent(value);
    setPanel(null);
    textareaRef.current?.focus();
  };

  // Close an open panel on Escape.
  useEffect(() => {
    if (!panel) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPanel(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [panel]);

  const toggleClass = (active: boolean) =>
    `rounded-lg border px-2.5 py-1 font-syne text-[11px] transition-colors ${
      active
        ? 'border-cyan/35 bg-cyan/20 text-cyan-100'
        : 'border-white/10 text-slate-300 hover:text-white'
    }`;

  return (
    <form onSubmit={handleSubmit} className="mb-6">
      <div className="intent-shell rounded-2xl p-5 md:p-6 panel-glow">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <label className="block font-syne text-sm font-semibold tracking-wide text-slate-200">
            Network Slice Intent
          </label>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => setPanel(panel === 'templates' ? null : 'templates')} className={toggleClass(panel === 'templates')}>
              Templates
            </button>
            <button
              type="button"
              onClick={() => setPanel(panel === 'history' ? null : 'history')}
              disabled={history.length === 0}
              className={`${toggleClass(panel === 'history')} disabled:opacity-40`}
            >
              Recent ({history.length})
            </button>
            <span className="rounded-md border border-cyan/40 bg-cyan/10 px-2 py-1 font-mono text-[11px] text-cyan">
              {parserLabel ?? 'NL → S-NSSAI'}
            </span>
          </div>
        </div>

        {panel === 'templates' && (
          <div className="mb-3 grid grid-cols-1 gap-2 rounded-xl border border-white/10 bg-black/20 p-3 sm:grid-cols-2">
            {INTENT_TEMPLATES.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => apply(template.intent)}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-left transition-colors hover:border-cyan/40"
              >
                <div className="flex items-center gap-2">
                  <span className="font-syne text-xs text-white">{template.label}</span>
                  <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                    {template.category}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] text-slate-400">{template.intent}</p>
                <p className="mt-1 font-mono text-[10px] text-cyan/70">{template.expects}</p>
              </button>
            ))}
          </div>
        )}

        {panel === 'history' && (
          <div className="mb-3 rounded-xl border border-white/10 bg-black/20 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-syne text-[11px] uppercase tracking-[0.14em] text-slate-400">
                Recent intents
              </span>
              <button
                type="button"
                onClick={onClearHistory}
                className="font-syne text-[11px] text-slate-400 hover:text-white"
              >
                Clear
              </button>
            </div>
            <ul className="max-h-48 space-y-1 overflow-y-auto">
              {history.map((entry) => (
                <li key={entry.at}>
                  <button
                    type="button"
                    onClick={() => apply(entry.intent)}
                    className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.05]"
                  >
                    <span
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        entry.succeeded ? 'bg-emerald-400' : 'bg-rose-400'
                      }`}
                    />
                    <span className="min-w-0 flex-1 truncate text-[11px] text-slate-300">
                      {entry.intent}
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-slate-500">
                      {new Date(entry.at).toLocaleTimeString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="mb-3 text-xs text-slate-300">
          Describe business goals, latency target, capacity, device count, and location.
        </p>

        <textarea
          ref={textareaRef}
          value={intent}
          onChange={(event) => setIntent(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={PLACEHOLDER}
          className="intent-textarea h-32 w-full resize-none rounded-md p-3 font-mono text-sm transition-all"
          disabled={busy}
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <span className="font-mono text-xs text-slate-400">
            {intent.length} characters
            <span className="ml-3 hidden text-slate-500 sm:inline">
              ⌘/Ctrl+Enter to provision · +Shift to dry run
            </span>
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => trimmed && onSimulate(trimmed)}
              disabled={!trimmed || busy}
              className="rounded-lg border border-white/15 px-3 py-2 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white disabled:opacity-40"
              title="Check whether this intent would deploy, without changing anything"
            >
              {simulating ? 'Checking...' : 'Dry run'}
            </button>
            <button
              type="submit"
              disabled={!trimmed || busy}
              className={`provision-btn flex items-center gap-2 ${
                !trimmed || busy ? 'provision-btn-disabled' : ''
              }`}
            >
              {loading && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              )}
              {loading ? 'Provisioning...' : 'Provision Slice'}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}
