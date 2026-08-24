import type { SlaStatus } from '../types/telemetry';

const PALETTE: Record<SlaStatus, { label: string; className: string; dot: string }> = {
  meeting: {
    label: 'Meeting SLA',
    className: 'bg-emerald-400/15 text-emerald-200 border-emerald-300/40',
    dot: 'bg-emerald-400',
  },
  at_risk: {
    label: 'At risk',
    className: 'bg-amber-300/15 text-amber-100 border-amber-200/40',
    dot: 'bg-amber-400',
  },
  violated: {
    label: 'SLA violated',
    className: 'bg-rose-400/15 text-rose-200 border-rose-300/40',
    dot: 'bg-rose-400',
  },
  unknown: {
    label: 'No data yet',
    className: 'bg-slate-400/10 text-slate-300 border-slate-400/30',
    dot: 'bg-slate-400',
  },
};

interface SlaBadgeProps {
  status: SlaStatus;
  score?: number;
  compact?: boolean;
}

export function SlaBadge({ status, score, compact = false }: SlaBadgeProps) {
  const palette = PALETTE[status] ?? PALETTE.unknown;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-syne ${palette.className}`}
      title={score !== undefined ? `Compliance score ${score.toFixed(1)} / 100` : palette.label}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${palette.dot} ${
          status === 'violated' ? 'animate-pulse' : ''
        }`}
      />
      {compact ? null : palette.label}
      {score !== undefined && status !== 'unknown' && (
        <span className="font-mono opacity-80">{score.toFixed(0)}</span>
      )}
    </span>
  );
}
