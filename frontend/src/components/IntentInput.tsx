import { useState } from 'react';

interface IntentInputProps {
  onSubmit: (intent: string) => void;
  loading: boolean;
}

export function IntentInput({ onSubmit, loading }: IntentInputProps) {
  const [intent, setIntent] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (intent.trim() && !loading) {
      onSubmit(intent.trim());
    }
  };

  const placeholder = `Describe your network slice requirement in plain English...

Example: "Create a high-security low-latency slice for 500 hospital devices in Chennai with guaranteed 50Mbps"`;

  return (
    <form onSubmit={handleSubmit} className="mb-6">
      <div className="intent-shell rounded-2xl p-5 md:p-6 panel-glow">
        <div className="flex items-center justify-between gap-3 mb-3">
          <label className="block text-slate-200 text-sm font-syne font-semibold tracking-wide">
            Network Slice Intent
          </label>
          <span className="text-[11px] font-mono text-cyan border border-cyan/40 rounded-md px-2 py-1 bg-cyan/10">
            NL → S-NSSAI
          </span>
        </div>
        <p className="text-xs text-slate-300 mb-3">
          Describe business goals, latency target, capacity, device count, and location.
        </p>
        <textarea
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder={placeholder}
          className="intent-textarea w-full h-32 rounded-md p-3 resize-none font-mono text-sm transition-all"
          disabled={loading}
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-slate-400 text-xs font-mono">
            {intent.length} characters
          </span>
          <button
            type="submit"
            disabled={!intent.trim() || loading}
            className={`provision-btn flex items-center gap-2 ${
              !intent.trim() || loading ? 'provision-btn-disabled' : ''
            }`}
          >
            {loading && (
              <svg
                className="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {loading ? 'Provisioning...' : 'Provision Slice'}
          </button>
        </div>
      </div>
    </form>
  );
}
