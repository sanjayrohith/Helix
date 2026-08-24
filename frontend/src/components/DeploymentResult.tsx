import { useState } from 'react';
import type { SliceDeploymentResult } from '../types/slice';
import { SST_NAMES } from '../types/slice';
import { ConflictAlert } from './ConflictAlert';

interface DeploymentResultProps {
  result: SliceDeploymentResult;
  onDismiss: () => void;
  onInspect?: (sliceId: string) => void;
}

function ParseProvenance({ result }: { result: SliceDeploymentResult }) {
  const [open, setOpen] = useState(false);
  const trace = result.parse_trace;

  return (
    <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.02] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-slate-300">
          parsed by {result.parser_used}
        </span>
        {result.parse_fallback_reason && (
          <span
            className="rounded bg-amber-300/20 px-1.5 py-0.5 font-mono text-amber-100"
            title={result.parse_fallback_reason}
          >
            LLM unavailable, used the deterministic parser
          </span>
        )}
        {trace?.matched_profile && (
          <span className="font-mono text-slate-400">
            matched the {trace.matched_profile} profile
          </span>
        )}
        {trace && (
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="ml-auto text-cyan hover:text-cyan-100"
          >
            {open ? 'Hide reasoning' : 'How was this derived?'}
          </button>
        )}
      </div>

      {open && trace && (
        <dl className="mt-2 space-y-1 border-l-2 border-white/10 pl-3">
          {Object.entries(trace.derived).map(([field, reason]) => (
            <div key={field} className="flex gap-2 text-[11px]">
              <dt className="shrink-0 font-mono text-cyan/80">{field}</dt>
              <dd className="text-slate-300">{reason}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

export function DeploymentResult({ result, onDismiss, onInspect }: DeploymentResultProps) {
  const { success, slice_config: config, conflict_report: report, deploy_time_seconds } = result;

  const dismissButton = (
    <button
      onClick={onDismiss}
      className="absolute right-3 top-3 z-10 text-slate-400 transition-colors hover:text-slate-200"
      aria-label="Dismiss"
    >
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  );

  if (!success) {
    return (
      <div className="relative mb-6">
        {dismissButton}
        <ConflictAlert conflict={report} />
        <ParseProvenance result={result} />
        <div className="mt-2 font-mono text-xs text-slate-400">
          Evaluated in {deploy_time_seconds.toFixed(2)}s
        </div>
      </div>
    );
  }

  return (
    <div className="relative mb-6 rounded-2xl border border-emerald-200/30 bg-emerald-300/10 p-5 backdrop-blur-sm">
      {dismissButton}

      <div className="mb-4 flex items-start gap-3">
        <svg
          className="mt-0.5 h-6 w-6 shrink-0 text-success"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div className="min-w-0">
          <h4 className="font-syne font-semibold text-emerald-200">{config.name}</h4>
          <p className="mt-0.5 text-xs text-slate-300">
            Deployed and activated in {deploy_time_seconds.toFixed(2)}s
          </p>
        </div>
        {onInspect && (
          <button
            onClick={() => onInspect(config.slice_id)}
            className="ml-auto mr-8 shrink-0 rounded-lg border border-white/15 px-3 py-1.5 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white"
          >
            Inspect
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-sm sm:grid-cols-4">
        <Field label="S-NSSAI" value={`SST=${config.sst} / ${config.sd}`} />
        <Field label="Type" value={SST_NAMES[config.sst] ?? String(config.sst)} />
        <Field label="5QI" value={String(config.qos_5qi)} />
        <Field label="ARP" value={String(config.arp_priority)} />
        <Field label="GBR" value={`${config.guaranteed_bitrate_mbps} Mbps`} />
        <Field label="Max" value={`${config.max_bitrate_mbps} Mbps`} />
        <Field label="Latency" value={`${config.latency_ms} ms`} />
        <Field label="Devices" value={config.device_count.toLocaleString()} />
      </div>

      {report.findings.length > 0 && (
        <div className="mt-3">
          <ConflictAlert conflict={report} />
        </div>
      )}

      <ParseProvenance result={result} />
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.12em] text-slate-400">{label}</div>
      <div className="truncate font-mono text-slate-100">{value}</div>
    </div>
  );
}
