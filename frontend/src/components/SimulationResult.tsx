import type { SliceSimulationResult } from '../types/slice';
import { SST_NAMES } from '../types/slice';
import { ConflictAlert } from './ConflictAlert';

interface SimulationResultProps {
  result: SliceSimulationResult;
  onDismiss: () => void;
  onProvisionAnyway: () => void;
}

function CapacityBar({ before, after }: { before: number; after: number }) {
  // The bar is scaled against whichever is larger so an over-capacity request
  // is visibly over rather than silently clipped at 100%.
  const scale = Math.max(after, before, 1);
  return (
    <div className="mt-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-white/10">
        <div className="bg-cyan/70" style={{ width: `${(before / scale) * 100}%` }} />
        <div
          className="bg-emerald-400/70"
          style={{ width: `${(Math.max(0, after - before) / scale) * 100}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-slate-400">
        <span>{before.toFixed(0)} Mbps in use</span>
        <span>+{(after - before).toFixed(0)} Mbps requested</span>
      </div>
    </div>
  );
}

export function SimulationResult({
  result,
  onDismiss,
  onProvisionAnyway,
}: SimulationResultProps) {
  const config = result.slice_config;
  const remediated = result.remediated_config;
  const remediationWorks = result.remediated_report
    ? !result.remediated_report.has_conflict
    : false;

  return (
    <div className="relative mb-6 rounded-2xl border border-white/15 bg-white/[0.04] p-5 backdrop-blur-sm">
      <button
        onClick={onDismiss}
        className="absolute right-3 top-3 text-slate-400 transition-colors hover:text-slate-200"
        aria-label="Dismiss"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-md border border-white/15 bg-white/[0.05] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-slate-300">
          dry run
        </span>
        <h4
          className={`font-syne font-semibold ${
            result.would_deploy ? 'text-emerald-200' : 'text-amber-100'
          }`}
        >
          {result.would_deploy
            ? 'This intent would deploy'
            : 'This intent would be blocked'}
        </h4>
        <span className="ml-auto font-mono text-[11px] text-slate-400">
          parsed by {result.parser_used}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm sm:grid-cols-4">
        <Field label="Type" value={SST_NAMES[config.sst] ?? String(config.sst)} />
        <Field label="5QI" value={String(config.qos_5qi)} />
        <Field label="ARP" value={String(config.arp_priority)} />
        <Field label="GBR" value={`${config.guaranteed_bitrate_mbps} Mbps`} />
        <Field label="Latency" value={`${config.latency_ms} ms`} />
        <Field label="Isolation" value={config.isolation} />
        <Field label="Devices" value={config.device_count.toLocaleString()} />
        <Field label="Location" value={config.location} />
      </div>

      <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3">
        <span className="font-syne text-xs text-slate-300">Capacity impact</span>
        <CapacityBar before={result.capacity_before_mbps} after={result.capacity_after_mbps} />
      </div>

      {result.conflict_report.findings.length > 0 && (
        <div className="mt-3">
          <ConflictAlert conflict={result.conflict_report} />
        </div>
      )}

      {!result.would_deploy && remediated && (
        <div
          className={`mt-3 rounded-xl border px-4 py-3 ${
            remediationWorks
              ? 'border-emerald-300/30 bg-emerald-400/[0.06]'
              : 'border-amber-200/30 bg-amber-300/[0.05]'
          }`}
        >
          <h5 className="font-syne text-xs text-white">
            {remediationWorks
              ? 'With the suggested changes applied, it would deploy'
              : 'Even with the suggested changes, conflicts remain'}
          </h5>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
            <Field label="GBR" value={`${remediated.guaranteed_bitrate_mbps} Mbps`} />
            <Field label="ARP" value={String(remediated.arp_priority)} />
            <Field label="Isolation" value={remediated.isolation} />
            <Field label="SD" value={remediated.sd} />
          </div>
        </div>
      )}

      {result.would_deploy && (
        <button
          onClick={onProvisionAnyway}
          className="provision-btn mt-4"
          type="button"
        >
          Provision this slice
        </button>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-slate-400">{label}</div>
      <div className="font-mono capitalize text-slate-100">{value}</div>
    </div>
  );
}
