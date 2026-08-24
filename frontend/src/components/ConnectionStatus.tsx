import type { ConnectionState } from '../services/websocket';

const LABELS: Record<ConnectionState, { text: string; dot: string; tone: string }> = {
  open: { text: 'Live', dot: 'bg-success pulse-dot', tone: 'text-slate-200' },
  connecting: { text: 'Connecting', dot: 'bg-amber-400 animate-pulse', tone: 'text-amber-100' },
  closed: { text: 'Offline', dot: 'bg-slate-500', tone: 'text-slate-400' },
  failed: { text: 'Disconnected', dot: 'bg-rose-400', tone: 'text-rose-200' },
};

interface ConnectionStatusProps {
  state: ConnectionState;
  onRetry: () => void;
}

export function ConnectionStatus({ state, onRetry }: ConnectionStatusProps) {
  const label = LABELS[state];

  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${label.dot}`} />
      <span className={`font-syne text-sm ${label.tone}`}>{label.text}</span>
      {state === 'failed' && (
        <button
          onClick={onRetry}
          className="rounded border border-white/15 px-2 py-0.5 font-syne text-[11px] text-slate-300 transition-colors hover:text-white"
        >
          Retry
        </button>
      )}
    </div>
  );
}
