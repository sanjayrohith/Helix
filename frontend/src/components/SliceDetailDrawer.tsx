import { useCallback, useEffect, useState } from 'react';
import {
  fetchExport,
  getPlacement,
  getSliceTelemetry,
  rebalanceSlice,
  resumeSlice,
  scaleSlice,
  suspendSlice,
} from '../services/api';
import type { SliceConfig } from '../types/slice';
import { SST_DESCRIPTIONS, SST_NAMES } from '../types/slice';
import type { PlacementDecision, TelemetrySnapshot } from '../types/telemetry';
import { SlaBadge } from './SlaBadge';
import { Sparkline } from './Sparkline';

interface SliceDetailDrawerProps {
  slice: SliceConfig | null;
  onClose: () => void;
  onChanged: () => void;
  onNotify: (message: string, type: 'success' | 'error' | 'warning') => void;
}

type Tab = 'performance' | 'configuration' | 'placement' | 'export';

const TABS: { id: Tab; label: string }[] = [
  { id: 'performance', label: 'Performance' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'placement', label: 'Placement' },
  { id: 'export', label: 'Export' },
];

const EXPORT_FORMATS = ['kubernetes', 'open5gs', 'snssai', 'flow-rules', 'json'];

export function SliceDetailDrawer({
  slice,
  onClose,
  onChanged,
  onNotify,
}: SliceDetailDrawerProps) {
  const [tab, setTab] = useState<Tab>('performance');
  const [telemetry, setTelemetry] = useState<TelemetrySnapshot | null>(null);
  const [placement, setPlacement] = useState<PlacementDecision | null>(null);
  const [exportFormat, setExportFormat] = useState('kubernetes');
  const [exportBody, setExportBody] = useState('');
  const [busy, setBusy] = useState(false);

  const sliceId = slice?.slice_id ?? null;

  const loadTelemetry = useCallback(async () => {
    if (!sliceId) return;
    try {
      setTelemetry(await getSliceTelemetry(sliceId, 60));
    } catch {
      setTelemetry(null);
    }
  }, [sliceId]);

  // Reset to the first tab whenever a different slice is opened.
  useEffect(() => {
    if (sliceId) setTab('performance');
  }, [sliceId]);

  useEffect(() => {
    if (!sliceId) return;
    loadTelemetry();
    const timer = setInterval(loadTelemetry, 4000);
    return () => clearInterval(timer);
  }, [sliceId, loadTelemetry]);

  useEffect(() => {
    if (!sliceId || tab !== 'placement') return;
    getPlacement(sliceId).then(setPlacement).catch(() => setPlacement(null));
  }, [sliceId, tab]);

  useEffect(() => {
    if (!sliceId || tab !== 'export') return;
    setExportBody('Loading...');
    fetchExport(exportFormat, sliceId)
      .then(setExportBody)
      .catch((error) => setExportBody(`Export failed: ${error.message}`));
  }, [sliceId, tab, exportFormat]);

  // Escape closes the drawer, matching the behaviour of every other overlay.
  useEffect(() => {
    if (!sliceId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [sliceId, onClose]);

  if (!slice) return null;

  const act = async (label: string, action: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await action();
      onNotify(`${label} succeeded`, 'success');
      onChanged();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : `${label} failed`, 'error');
    } finally {
      setBusy(false);
    }
  };

  const history = telemetry?.history ?? [];
  const latest = telemetry?.latest;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="fixed right-0 top-0 z-50 flex h-full w-full max-w-xl flex-col border-l border-white/10 bg-[#0b1225] shadow-2xl"
        role="dialog"
        aria-label={`Details for ${slice.name}`}
      >
        <header className="border-b border-white/10 px-5 py-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate font-syne text-lg text-white">{slice.name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded border border-cyan/30 bg-cyan/10 px-2 py-0.5 font-mono text-cyan">
                  {SST_NAMES[slice.sst]}
                </span>
                <span className="text-slate-400">{SST_DESCRIPTIONS[slice.sst]}</span>
                {telemetry?.sla && (
                  <SlaBadge
                    status={telemetry.sla.status}
                    score={telemetry.sla.compliance_score}
                  />
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded p-1 text-slate-400 transition-colors hover:text-white"
              aria-label="Close"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <nav className="mt-4 flex gap-1">
            {TABS.map((entry) => (
              <button
                key={entry.id}
                onClick={() => setTab(entry.id)}
                className={`rounded-lg px-3 py-1.5 font-syne text-xs transition-all ${
                  tab === entry.id
                    ? 'border border-cyan/35 bg-cyan/20 text-cyan-100'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                {entry.label}
              </button>
            ))}
          </nav>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === 'performance' && (
            <PerformanceTab history={history} latest={latest ?? null} slice={slice} />
          )}
          {tab === 'configuration' && <ConfigurationTab slice={slice} />}
          {tab === 'placement' && <PlacementTab placement={placement} />}
          {tab === 'export' && (
            <ExportTab
              format={exportFormat}
              body={exportBody}
              onFormatChange={setExportFormat}
              onCopy={() => {
                navigator.clipboard
                  ?.writeText(exportBody)
                  .then(() => onNotify('Copied to clipboard', 'success'))
                  .catch(() => onNotify('Could not access the clipboard', 'warning'));
              }}
            />
          )}
        </div>

        <footer className="flex flex-wrap gap-2 border-t border-white/10 px-5 py-3">
          <button
            disabled={busy}
            onClick={() => act('Scale up', () => scaleSlice(slice.slice_id, 1.5))}
            className="rounded-lg border border-white/15 px-3 py-1.5 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white disabled:opacity-40"
          >
            Scale 1.5x
          </button>
          <button
            disabled={busy}
            onClick={() => act('Scale down', () => scaleSlice(slice.slice_id, 0.75))}
            className="rounded-lg border border-white/15 px-3 py-1.5 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white disabled:opacity-40"
          >
            Scale 0.75x
          </button>
          {slice.status === 'active' ? (
            <button
              disabled={busy}
              onClick={() => act('Suspend', () => suspendSlice(slice.slice_id))}
              className="rounded-lg border border-amber-200/30 px-3 py-1.5 font-syne text-xs text-amber-100 transition-colors hover:border-amber-200/60 disabled:opacity-40"
            >
              Suspend
            </button>
          ) : (
            <button
              disabled={busy}
              onClick={() => act('Resume', () => resumeSlice(slice.slice_id))}
              className="rounded-lg border border-emerald-300/30 px-3 py-1.5 font-syne text-xs text-emerald-200 transition-colors hover:border-emerald-300/60 disabled:opacity-40"
            >
              Resume
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => act('Rebalance', () => rebalanceSlice(slice.slice_id))}
            className="ml-auto rounded-lg border border-white/15 px-3 py-1.5 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white disabled:opacity-40"
          >
            Rebalance
          </button>
        </footer>
      </aside>
    </>
  );
}

function PerformanceTab({
  history,
  latest,
  slice,
}: {
  history: TelemetrySnapshot['history'];
  latest: TelemetrySnapshot['latest'];
  slice: SliceConfig;
}) {
  if (!latest) {
    return (
      <p className="text-sm text-slate-400">
        No telemetry yet. Samples appear once the monitor loop has run an interval.
      </p>
    );
  }

  const charts = [
    {
      label: 'Throughput',
      unit: 'Mbps',
      value: latest.throughput_mbps,
      series: history.map((point) => point.throughput_mbps),
      color: '#00d4ff',
    },
    {
      label: 'Latency',
      unit: 'ms',
      value: latest.latency_ms,
      series: history.map((point) => point.latency_ms),
      color: '#ffb800',
      threshold: slice.latency_ms,
    },
    {
      label: 'Jitter',
      unit: 'ms',
      value: latest.jitter_ms,
      series: history.map((point) => point.jitter_ms),
      color: '#a78bfa',
    },
    {
      label: 'Packet loss',
      unit: '%',
      value: latest.packet_loss_percent,
      series: history.map((point) => point.packet_loss_percent),
      color: '#ff4444',
    },
    {
      label: 'PRB utilisation',
      unit: '%',
      value: latest.prb_utilization_percent,
      series: history.map((point) => point.prb_utilization_percent),
      color: '#00ff88',
    },
    {
      label: 'Offered load',
      unit: 'Mbps',
      value: latest.offered_load_mbps,
      series: history.map((point) => point.offered_load_mbps),
      color: '#38bdf8',
    },
  ];

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {charts.map((chart) => (
          <div
            key={chart.label}
            className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2"
          >
            <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">
              {chart.label}
            </div>
            <div className="mt-0.5 font-mono text-lg text-white">
              {chart.value.toFixed(2)}
              <span className="ml-1 text-xs text-slate-400">{chart.unit}</span>
            </div>
            <Sparkline
              values={chart.series}
              color={chart.color}
              threshold={chart.threshold}
              width={180}
              height={34}
              label={chart.label}
            />
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm">
        <div className="flex justify-between py-1">
          <span className="text-slate-400">Attached devices</span>
          <span className="font-mono text-white">
            {latest.active_devices.toLocaleString()} / {slice.device_count.toLocaleString()}
          </span>
        </div>
        <div className="flex justify-between py-1">
          <span className="text-slate-400">Availability</span>
          <span className="font-mono text-white">{latest.availability_percent.toFixed(3)}%</span>
        </div>
        <div className="flex justify-between py-1">
          <span className="text-slate-400">Samples retained</span>
          <span className="font-mono text-white">{history.length}</span>
        </div>
      </div>
    </div>
  );
}

function ConfigurationTab({ slice }: { slice: SliceConfig }) {
  const rows: [string, string][] = [
    ['S-NSSAI', `SST=${slice.sst} / SD=${slice.sd}`],
    ['5QI', String(slice.qos_5qi)],
    ['ARP priority', `${slice.arp_priority} (1 = highest)`],
    ['Guaranteed bitrate', `${slice.guaranteed_bitrate_mbps} Mbps`],
    ['Maximum bitrate', `${slice.max_bitrate_mbps} Mbps`],
    ['Latency target', `${slice.latency_ms} ms`],
    ['Isolation', slice.isolation],
    ['Security level', slice.security_level],
    ['Devices', slice.device_count.toLocaleString()],
    ['Use case', slice.use_case],
    ['Location', slice.location],
    ['Status', slice.status],
    ['Created', new Date(slice.created_at).toLocaleString()],
    ['Updated', slice.updated_at ? new Date(slice.updated_at).toLocaleString() : 'never'],
  ];

  return (
    <dl className="divide-y divide-white/5 rounded-xl border border-white/10 bg-white/[0.03]">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between px-4 py-2 text-sm">
          <dt className="font-syne text-slate-400">{label}</dt>
          <dd className="font-mono capitalize text-white">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function PlacementTab({ placement }: { placement: PlacementDecision | null }) {
  if (!placement) return <p className="text-sm text-slate-400">Loading placement...</p>;

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
        <div className="font-syne text-sm text-white">
          {placement.placed ? placement.node_name : 'Not placed'}
        </div>
        <p className="mt-1 text-xs text-slate-300">{placement.explanation}</p>
      </div>

      <div>
        <h3 className="mb-2 font-syne text-xs uppercase tracking-[0.14em] text-slate-400">
          Candidate nodes
        </h3>
        <ul className="space-y-2">
          {placement.candidates.map((candidate) => (
            <li
              key={candidate.node_id}
              className={`rounded-xl border px-3 py-2 ${
                candidate.node_id === placement.node_id
                  ? 'border-cyan/40 bg-cyan/[0.08]'
                  : candidate.feasible
                  ? 'border-white/10 bg-white/[0.03]'
                  : 'border-white/5 bg-white/[0.015] opacity-60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-syne text-sm text-white">{candidate.node_name}</span>
                <span
                  className={`font-mono text-xs ${
                    candidate.feasible ? 'text-cyan' : 'text-rose-300'
                  }`}
                >
                  {candidate.feasible ? candidate.score.toFixed(1) : 'infeasible'}
                </span>
              </div>
              <ul className="mt-1 space-y-0.5">
                {candidate.reasons.map((reason) => (
                  <li key={reason} className="text-[11px] text-slate-400">
                    {reason}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ExportTab({
  format,
  body,
  onFormatChange,
  onCopy,
}: {
  format: string;
  body: string;
  onFormatChange: (value: string) => void;
  onCopy: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {EXPORT_FORMATS.map((entry) => (
          <button
            key={entry}
            onClick={() => onFormatChange(entry)}
            className={`rounded-lg px-2.5 py-1 font-mono text-xs transition-all ${
              format === entry
                ? 'border border-cyan/35 bg-cyan/20 text-cyan-100'
                : 'border border-white/10 text-slate-300 hover:text-white'
            }`}
          >
            {entry}
          </button>
        ))}
        <button
          onClick={onCopy}
          className="ml-auto rounded-lg border border-white/15 px-2.5 py-1 font-syne text-xs text-slate-200 hover:text-white"
        >
          Copy
        </button>
      </div>
      <pre className="max-h-[60vh] overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-slate-200">
        {body}
      </pre>
    </div>
  );
}
