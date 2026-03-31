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
      <div className="bg-navy-800 border border-navy-600 rounded-lg p-4">
        <label className="block text-gray-300 text-sm font-medium mb-2">
          Network Slice Intent
        </label>
        <textarea
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder={placeholder}
          className="w-full h-32 bg-navy-900 border border-navy-600 rounded-lg p-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-400 resize-none font-mono text-sm"
          disabled={loading}
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-gray-500 text-xs">
            {intent.length} characters
          </span>
          <button
            type="submit"
            disabled={!intent.trim() || loading}
            className={`px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
              !intent.trim() || loading
                ? 'bg-navy-600 text-gray-500 cursor-not-allowed'
                : 'bg-cyan-500 text-navy-900 hover:bg-cyan-400'
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
