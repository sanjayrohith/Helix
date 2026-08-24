import { useState } from 'react';
import type { SlaEvaluation } from '../types/telemetry';
import { SlaBadge } from './SlaBadge';

interface SlaAlertPanelProps {
  evaluations: SlaEvaluation[];
  onInspect: (sliceId: string) => void;
}

const KPI_LABELS: Record<string, string> = {
  latency: 'Latency',
  throughput: 'Throughput',
  packet_loss: 'Packet loss',
  jitter: 'Jitter',
  availability: 'Availability',
  prb_utilization: 'PRB utilisation',
};

export function SlaAlertPanel({ evaluations, onInspect }: SlaAlertPanelProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const breaching = evaluations
    .filter((evaluation) => evaluation.status === 'violated' || evaluation.status === 'at_risk')
    // Worst first: violations before risks, then by score.
    .sort((a, b) => {
      const rank = (status: string) => (status === 'violated' ? 0 : 1);
      return rank(a.status) - rank(b.status) || a.compliance_score - b.compliance_score;
    });

  if (breaching.length === 0) {
    return (
      <section className="mb-6 rounded-2xl border border-emerald-300/20 bg-emerald-400/[0.06] px-4 py-3">
        <div className="flex items-center gap-2 font-syne text-sm text-emerald-200">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Every active slice is meeting its SLA.
        </div>
      </section>
    );
  }

  return (
    <section className="mb-6 rounded-2xl border border-amber-200/25 bg-amber-300/[0.06]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <h2 className="font-syne text-sm text-amber-100">
          {breaching.length} slice{breaching.length === 1 ? '' : 's'} outside SLA
        </h2>
        <span className="text-[11px] font-mono text-slate-400">
          worst compliance {breaching[0].compliance_score.toFixed(0)}/100
        </span>
      </div>

      <ul className="divide-y divide-white/5">
        {breaching.map((evaluation) => {
          const open = expanded === evaluation.slice_id;
          return (
            <li key={evaluation.slice_id} className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-3">
                <SlaBadge status={evaluation.status} score={evaluation.compliance_score} />
                <span className="min-w-0 flex-1 truncate font-syne text-sm text-white">
                  {evaluation.slice_name}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {evaluation.breaches.map((breach) => (
                    <span
                      key={breach.kpi}
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${
                        breach.severity === 'critical'
                          ? 'bg-rose-400/20 text-rose-200'
                          : 'bg-amber-300/20 text-amber-100'
                      }`}
                    >
                      {KPI_LABELS[breach.kpi] ?? breach.kpi}
                    </span>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setExpanded(open ? null : evaluation.slice_id)}
                  className="text-xs text-cyan hover:text-cyan-100"
                >
                  {open ? 'Hide' : 'Why?'}
                </button>
                <button
                  type="button"
                  onClick={() => onInspect(evaluation.slice_id)}
                  className="text-xs text-slate-300 hover:text-white"
                >
                  Inspect
                </button>
              </div>

              {open && (
                <ul className="mt-2 space-y-1 border-l-2 border-white/10 pl-3">
                  {evaluation.breaches.map((breach) => (
                    <li key={breach.kpi} className="text-xs text-slate-300">
                      {breach.description}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
