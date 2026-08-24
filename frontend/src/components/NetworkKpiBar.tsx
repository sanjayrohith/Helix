import { Sparkline } from './Sparkline';
import type { NetworkKpiSummary } from '../types/telemetry';

interface NetworkKpiBarProps {
  summary: NetworkKpiSummary | null;
  /** Recent summaries, oldest first, for the trend sparklines. */
  history: NetworkKpiSummary[];
  live: boolean;
}

function Metric({
  label,
  value,
  unit,
  series,
  color,
  hint,
}: {
  label: string;
  value: string;
  unit?: string;
  series: number[];
  color: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3" title={hint}>
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400 font-syne">
        {label}
      </div>
      <div className="mt-1 flex items-end justify-between gap-3">
        <div className="font-mono text-xl text-white">
          {value}
          {unit && <span className="ml-1 text-xs text-slate-400">{unit}</span>}
        </div>
        <Sparkline values={series} color={color} width={72} height={26} label={label} />
      </div>
    </div>
  );
}

export function NetworkKpiBar({ summary, history, live }: NetworkKpiBarProps) {
  if (!summary) {
    return (
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((index) => (
          <div
            key={index}
            className="h-[76px] animate-pulse rounded-xl border border-white/10 bg-white/[0.03]"
          />
        ))}
      </div>
    );
  }

  const totalGraded =
    summary.slices_meeting_sla + summary.slices_at_risk + summary.slices_violating_sla;

  return (
    <section className="mb-6">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-syne text-sm text-slate-200">Live network performance</h2>
        <span className="flex items-center gap-1.5 text-[11px] font-syne text-slate-400">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              live ? 'bg-emerald-400 pulse-dot' : 'bg-slate-500'
            }`}
          />
          {live ? 'streaming' : 'paused'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          label="Throughput"
          value={summary.total_throughput_mbps.toFixed(1)}
          unit="Mbps"
          series={history.map((point) => point.total_throughput_mbps)}
          color="#00d4ff"
          hint="Delivered throughput summed across every active slice"
        />
        <Metric
          label="Mean latency"
          value={summary.mean_latency_ms.toFixed(1)}
          unit="ms"
          series={history.map((point) => point.mean_latency_ms)}
          color="#ffb800"
          hint="Mean observed latency across active slices"
        />
        <Metric
          label="Packet loss"
          value={summary.mean_packet_loss_percent.toFixed(3)}
          unit="%"
          series={history.map((point) => point.mean_packet_loss_percent)}
          color="#ff4444"
          hint="Mean packet loss across active slices"
        />
        <Metric
          label="PRB utilisation"
          value={summary.mean_prb_utilization_percent.toFixed(1)}
          unit="%"
          series={history.map((point) => point.mean_prb_utilization_percent)}
          color="#00ff88"
          hint="Mean physical resource block utilisation"
        />
      </div>

      {totalGraded > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-4 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-xs font-syne">
          <span className="text-slate-400">SLA compliance</span>
          <span className="flex items-center gap-1.5 text-emerald-200">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            {summary.slices_meeting_sla} meeting
          </span>
          <span className="flex items-center gap-1.5 text-amber-100">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            {summary.slices_at_risk} at risk
          </span>
          <span className="flex items-center gap-1.5 text-rose-200">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
            {summary.slices_violating_sla} violating
          </span>
          <div className="ml-auto hidden h-1.5 w-40 overflow-hidden rounded-full bg-white/10 sm:flex">
            <div
              className="bg-emerald-400"
              style={{ width: `${(summary.slices_meeting_sla / totalGraded) * 100}%` }}
            />
            <div
              className="bg-amber-400"
              style={{ width: `${(summary.slices_at_risk / totalGraded) * 100}%` }}
            />
            <div
              className="bg-rose-400"
              style={{ width: `${(summary.slices_violating_sla / totalGraded) * 100}%` }}
            />
          </div>
        </div>
      )}
    </section>
  );
}
