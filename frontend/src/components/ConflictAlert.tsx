import { useState } from 'react';
import type { ConflictFinding, ConflictReport, SliceConfig } from '../types/slice';

interface ConflictAlertProps {
  conflict: ConflictReport;
  /** Called with the engine's proposed changes so the caller can retry. */
  onApplyRemediation?: (changes: Partial<Record<keyof SliceConfig, string | number>>) => void;
}

const TYPE_LABELS: Record<string, string> = {
  bandwidth: 'Bandwidth capacity',
  snssai: 'S-NSSAI collision',
  arp: 'ARP priority',
  regulatory: 'Regulatory policy',
  latency: 'Latency feasibility',
  isolation: 'Isolation consistency',
  device_density: 'Device density',
};

const SEVERITY_STYLES: Record<string, string> = {
  blocking: 'border-rose-300/40 bg-rose-400/[0.08]',
  warning: 'border-amber-200/40 bg-amber-300/[0.07]',
  advisory: 'border-white/15 bg-white/[0.03]',
};

const SEVERITY_CHIP: Record<string, string> = {
  blocking: 'bg-rose-400/20 text-rose-200',
  warning: 'bg-amber-300/20 text-amber-100',
  advisory: 'bg-slate-400/15 text-slate-300',
};

function FieldChanges({
  changes,
}: {
  changes: Partial<Record<keyof SliceConfig, string | number>>;
}) {
  const entries = Object.entries(changes);
  if (entries.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {entries.map(([field, value]) => (
        <span
          key={field}
          className="rounded bg-cyan/15 px-1.5 py-0.5 font-mono text-[10px] text-cyan-100"
        >
          {field} → {String(value)}
        </span>
      ))}
    </div>
  );
}

function Finding({ finding }: { finding: ConflictFinding }) {
  const [open, setOpen] = useState(finding.severity === 'blocking');

  return (
    <li className={`rounded-xl border px-3 py-2.5 ${SEVERITY_STYLES[finding.severity]}`}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 text-left"
      >
        <span
          className={`rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide ${
            SEVERITY_CHIP[finding.severity]
          }`}
        >
          {finding.severity}
        </span>
        <span className="flex-1 font-syne text-sm text-white">
          {TYPE_LABELS[finding.conflict_type] ?? finding.conflict_type}
        </span>
        <svg
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="mt-2">
          <p className="text-xs leading-relaxed text-slate-200">{finding.details}</p>
          {finding.suggestions.length > 0 && (
            <ul className="mt-2 space-y-1">
              {finding.suggestions.map((suggestion) => (
                <li key={suggestion} className="flex gap-2 text-[11px] text-slate-300">
                  <span className="text-cyan">→</span>
                  <span>{suggestion}</span>
                </li>
              ))}
            </ul>
          )}
          <FieldChanges changes={finding.remediation} />
        </div>
      )}
    </li>
  );
}

export function ConflictAlert({ conflict, onApplyRemediation }: ConflictAlertProps) {
  const findings = conflict.findings ?? [];
  const blocking = findings.filter((finding) => finding.severity === 'blocking');
  const hasRemediation = Object.keys(conflict.auto_remediation ?? {}).length > 0;

  // Older payloads without per-finding detail still render their summary.
  if (findings.length === 0) {
    return (
      <div className="rounded-2xl border border-rose-300/40 bg-rose-400/[0.08] p-5">
        <h4 className="font-syne text-rose-200">Conflict detected</h4>
        <p className="mt-1 text-sm text-slate-200">{conflict.details}</p>
      </div>
    );
  }

  return (
    <div
      className={`rounded-2xl border p-5 ${
        conflict.has_conflict
          ? 'border-rose-300/40 bg-rose-400/[0.06]'
          : 'border-amber-200/30 bg-amber-300/[0.05]'
      }`}
    >
      <div className="mb-3 flex items-start gap-3">
        <svg
          className={`mt-0.5 h-5 w-5 shrink-0 ${
            conflict.has_conflict ? 'text-rose-300' : 'text-amber-200'
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <div className="min-w-0">
          <h4
            className={`font-syne font-semibold ${
              conflict.has_conflict ? 'text-rose-200' : 'text-amber-100'
            }`}
          >
            {conflict.has_conflict
              ? `${blocking.length} conflict${blocking.length === 1 ? '' : 's'} blocked this deployment`
              : `Deployed with ${findings.length} advisory finding${findings.length === 1 ? '' : 's'}`}
          </h4>
          <p className="mt-0.5 text-xs text-slate-300">
            {findings.length} check{findings.length === 1 ? '' : 's'} produced a finding.
            {blocking.length < findings.length &&
              ` ${findings.length - blocking.length} of them are advisory.`}
          </p>
        </div>
      </div>

      <ul className="space-y-2">
        {findings.map((finding, index) => (
          <Finding key={`${finding.conflict_type}-${index}`} finding={finding} />
        ))}
      </ul>

      {hasRemediation && (
        <div className="mt-4 rounded-xl border border-cyan/25 bg-cyan/[0.06] px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <span className="font-syne text-xs text-cyan-100">
                Suggested configuration that would deploy
              </span>
              <FieldChanges changes={conflict.auto_remediation} />
            </div>
            {onApplyRemediation && (
              <button
                type="button"
                onClick={() => onApplyRemediation(conflict.auto_remediation)}
                className="shrink-0 rounded-lg border border-cyan/40 bg-cyan/15 px-3 py-1.5 font-syne text-xs text-cyan-100 transition-colors hover:bg-cyan/25"
              >
                Apply and retry
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
