import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { POLL_INTERVAL_MS, SPARKLINE_POINTS } from './config';
import { ActivityFeed } from './components/ActivityFeed';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ConnectionStatus } from './components/ConnectionStatus';
import { DeploymentResult } from './components/DeploymentResult';
import { IntentInput } from './components/IntentInput';
import { NetworkKpiBar } from './components/NetworkKpiBar';
import { SimulationResult } from './components/SimulationResult';
import { SlaAlertPanel } from './components/SlaAlertPanel';
import { SliceDashboard } from './components/SliceDashboard';
import {
  applyFilters,
  DEFAULT_FILTERS,
  SliceFilterBar,
  type SliceFilters,
} from './components/SliceFilterBar';
import { SliceDetailDrawer } from './components/SliceDetailDrawer';
import { StatsBar } from './components/StatsBar';
import { TopologyPanel } from './components/TopologyPanel';
import { useIntentHistory } from './hooks/useIntentHistory';
import {
  deleteSlice,
  getAllSlices,
  getParserStatus,
  getSlaEvaluations,
  getSliceStats,
  getTelemetrySummary,
  provisionSlice,
  simulateSlice,
} from './services/api';
import { websocketService, type ConnectionState } from './services/websocket';
import type {
  SliceConfig,
  SliceDeploymentResult,
  SliceSimulationResult,
  SliceStats,
  WebSocketMessage,
} from './types/slice';
import type { NetworkKpiSummary, SlaEvaluation } from './types/telemetry';

type VisualMode = 'cinematic' | 'minimal';
type ToastType = 'success' | 'error' | 'warning';

function App() {
  const [slices, setSlices] = useState<SliceConfig[]>([]);
  const [stats, setStats] = useState<SliceStats | null>(null);
  const [kpiSummary, setKpiSummary] = useState<NetworkKpiSummary | null>(null);
  const [kpiHistory, setKpiHistory] = useState<NetworkKpiSummary[]>([]);
  const [slaEvaluations, setSlaEvaluations] = useState<SlaEvaluation[]>([]);
  const [deploymentResult, setDeploymentResult] = useState<SliceDeploymentResult | null>(null);
  const [simulation, setSimulation] = useState<SliceSimulationResult | null>(null);
  const [simulatedIntent, setSimulatedIntent] = useState('');
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [deletingSliceId, setDeletingSliceId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
  const [filters, setFilters] = useState<SliceFilters>(DEFAULT_FILTERS);
  const [selectedSliceId, setSelectedSliceId] = useState<string | null>(null);
  const [connection, setConnection] = useState<ConnectionState>('closed');
  const [parserLabel, setParserLabel] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [visualMode, setVisualMode] = useState<VisualMode>(() => {
    try {
      return localStorage.getItem('helix.visualMode') === 'minimal' ? 'minimal' : 'cinematic';
    } catch {
      return 'cinematic';
    }
  });

  const { history, record, clear } = useIntentHistory();
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  const showToast = useCallback((message: string, type: ToastType) => {
    setToast({ message, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 5000);
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const [slicesData, statsData] = await Promise.all([getAllSlices(), getSliceStats()]);
      setSlices(slicesData);
      setStats(statsData);
      setRefreshKey((key) => key + 1);
    } catch {
      showToast('Cannot reach the HELIX backend', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  const fetchTelemetry = useCallback(async () => {
    try {
      const [summary, evaluations] = await Promise.all([
        getTelemetrySummary(),
        getSlaEvaluations(),
      ]);
      setKpiSummary(summary);
      setKpiHistory((previous) => [...previous, summary].slice(-SPARKLINE_POINTS));
      setSlaEvaluations(evaluations);
    } catch {
      // Telemetry is supplementary; a failure here should not blank the page.
    }
  }, []);

  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.event) {
        case 'slice_created':
          setSlices((previous) => {
            const incoming = message.data as unknown as SliceConfig;
            // The provisioning response may have already added it.
            if (previous.some((slice) => slice.slice_id === incoming.slice_id)) return previous;
            return [...previous, incoming];
          });
          getSliceStats().then(setStats).catch(() => undefined);
          break;
        case 'slice_updated': {
          const incoming = message.data as unknown as SliceConfig;
          setSlices((previous) =>
            previous.map((slice) => (slice.slice_id === incoming.slice_id ? incoming : slice)),
          );
          getSliceStats().then(setStats).catch(() => undefined);
          break;
        }
        case 'slice_deleted': {
          const { slice_id: removedId } = message.data as { slice_id: string };
          setSlices((previous) => previous.filter((slice) => slice.slice_id !== removedId));
          setSelectedSliceId((current) => (current === removedId ? null : current));
          getSliceStats().then(setStats).catch(() => undefined);
          break;
        }
        case 'conflict_detected':
          showToast(
            `Conflict: ${(message.data as { conflict_type: string }).conflict_type}`,
            'warning',
          );
          break;
        case 'telemetry': {
          // The monitor loop pushes summary and SLA state together, so the
          // dashboard does not need to poll while the socket is open.
          const payload = message.data as {
            summary?: NetworkKpiSummary;
            sla?: SlaEvaluation[];
          };
          if (payload.summary) {
            setKpiSummary(payload.summary);
            setKpiHistory((previous) => [...previous, payload.summary!].slice(-SPARKLINE_POINTS));
          }
          if (payload.sla) setSlaEvaluations(payload.sla);
          break;
        }
      }
    },
    [showToast],
  );

  useEffect(() => {
    fetchData();
    fetchTelemetry();
    getParserStatus()
      .then((status) =>
        setParserLabel(status.active_parser === 'llm' ? `LLM · ${status.llm_model}` : 'Rule-based parser'),
      )
      .catch(() => undefined);

    websocketService.connect();
    const unsubscribeMessages = websocketService.subscribe('all', handleWebSocketMessage);
    const unsubscribeState = websocketService.onStateChange(setConnection);

    return () => {
      unsubscribeMessages();
      unsubscribeState();
      websocketService.disconnect();
    };
  }, [fetchData, fetchTelemetry, handleWebSocketMessage]);

  // Fall back to polling only while the socket is not delivering updates.
  useEffect(() => {
    if (connection === 'open') return;
    const timer = setInterval(() => {
      fetchData();
      fetchTelemetry();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [connection, fetchData, fetchTelemetry]);

  useEffect(() => {
    try {
      localStorage.setItem('helix.visualMode', visualMode);
    } catch {
      // Ignore storage failures; the mode simply will not persist.
    }
  }, [visualMode]);

  const handleProvision = async (intent: string) => {
    setProvisioning(true);
    setSimulation(null);
    setDeploymentResult(null);
    try {
      const result = await provisionSlice(intent);
      setDeploymentResult(result);
      record(intent, result.success);
      if (result.success) {
        showToast(`'${result.slice_config.name}' deployed`, 'success');
        fetchData();
        fetchTelemetry();
      } else {
        showToast('Provisioning blocked by a conflict', 'warning');
      }
    } catch (error) {
      record(intent, false);
      showToast(error instanceof Error ? error.message : 'Provisioning failed', 'error');
    } finally {
      setProvisioning(false);
    }
  };

  const handleSimulate = async (intent: string) => {
    setSimulating(true);
    setDeploymentResult(null);
    try {
      const result = await simulateSlice(intent, true);
      setSimulation(result);
      setSimulatedIntent(intent);
      showToast(
        result.would_deploy ? 'This intent would deploy' : 'This intent would be blocked',
        result.would_deploy ? 'success' : 'warning',
      );
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Dry run failed', 'error');
    } finally {
      setSimulating(false);
    }
  };

  const handleDeleteSlice = async (sliceId: string) => {
    setDeletingSliceId(sliceId);
    try {
      const result = await deleteSlice(sliceId);
      showToast(`Deleted, ${result.released_mbps.toFixed(0)} Mbps released`, 'success');
      setSelectedSliceId((current) => (current === sliceId ? null : current));
      fetchData();
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Delete failed', 'error');
    } finally {
      setDeletingSliceId(null);
    }
  };

  const visibleSlices = useMemo(() => applyFilters(slices, filters), [slices, filters]);
  const selectedSlice = useMemo(
    () => slices.find((slice) => slice.slice_id === selectedSliceId) ?? null,
    [slices, selectedSliceId],
  );

  return (
    <div
      className={`helix-app helix-theme-${visualMode} relative min-h-screen overflow-x-hidden text-primary`}
    >
      <div
        className={`pointer-events-none absolute inset-0 ${visualMode === 'minimal' ? 'opacity-40' : ''}`}
      >
        <div
          className={`absolute -top-24 left-1/3 h-72 w-72 rounded-full bg-cyan/15 blur-3xl ${
            visualMode === 'minimal' ? 'hidden md:block' : ''
          }`}
        />
        <div
          className={`absolute -left-20 top-64 h-80 w-80 rounded-full bg-sky-500/15 blur-3xl ${
            visualMode === 'minimal' ? 'hidden md:block' : ''
          }`}
        />
        <div className="absolute bottom-20 right-0 h-96 w-96 rounded-full bg-emerald-400/10 blur-3xl" />
      </div>

      <header className="helix-header sticky top-0 z-30 border-b border-white/10 bg-[#0b1225]/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              <div className="helix-logo flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 via-cyan to-cyan-600 shadow-[0_0_20px_rgba(0,212,255,0.35)] ring-1 ring-cyan/70">
                <svg className="h-6 w-6 text-background" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <div>
                <h1 className="font-syne text-xl font-bold tracking-wide text-white">HELIX</h1>
                <div className="flex items-center gap-2">
                  <p className="text-xs text-slate-300">5G Intent-Based Network Slicing</p>
                  <span className="rounded border border-cyan/50 bg-cyan/10 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.12em] text-cyan">
                    Orchestrator
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between gap-4 md:justify-end">
              <div className="mode-switch flex items-center gap-1 rounded-xl border border-white/15 bg-white/[0.04] p-1">
                {(['cinematic', 'minimal'] as VisualMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setVisualMode(mode)}
                    className={`rounded-lg px-3 py-1.5 font-syne text-xs font-semibold capitalize tracking-wide transition-all ${
                      visualMode === mode
                        ? 'border border-cyan/35 bg-cyan/20 text-cyan-100'
                        : 'text-slate-300 hover:text-white'
                    }`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
              <ConnectionStatus state={connection} onRetry={() => websocketService.retry()} />
            </div>
          </div>
        </div>
      </header>

      {toast && (
        <div
          className={`fixed right-4 top-20 z-50 rounded-xl px-4 py-3 shadow-2xl backdrop-blur-xl transition-all ${
            toast.type === 'success'
              ? 'border border-emerald-300/40 bg-emerald-400/15 text-emerald-200'
              : toast.type === 'error'
              ? 'border border-rose-300/40 bg-rose-400/15 text-rose-200'
              : 'border border-amber-200/40 bg-amber-300/20 text-amber-100'
          }`}
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center gap-2 font-syne">
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="ml-2 opacity-70 transition-opacity hover:opacity-100"
              aria-label="Dismiss"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <main className="relative z-10 mx-auto max-w-7xl px-4 py-8 md:py-10">
        <section className="reveal-up mb-6 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 backdrop-blur-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan/80">
            Operational Visibility
          </p>
          <h2 className="font-syne text-lg text-slate-100 md:text-xl">
            Intent to deployment, in one control plane.
          </h2>
        </section>

        <div className="reveal-up reveal-delay-1">
          <StatsBar stats={stats} loading={loading} />
        </div>

        <div className="reveal-up reveal-delay-1">
          <ErrorBoundary section="Network KPIs">
            <NetworkKpiBar
              summary={kpiSummary}
              history={kpiHistory}
              live={connection === 'open'}
            />
          </ErrorBoundary>
        </div>

        <div className="reveal-up reveal-delay-2">
          <ErrorBoundary section="SLA alerts">
            <SlaAlertPanel evaluations={slaEvaluations} onInspect={setSelectedSliceId} />
          </ErrorBoundary>
        </div>

        <div className="reveal-up reveal-delay-2">
          <IntentInput
            onSubmit={handleProvision}
            onSimulate={handleSimulate}
            loading={provisioning}
            simulating={simulating}
            history={history}
            onClearHistory={clear}
            parserLabel={parserLabel}
          />
        </div>

        {simulation && (
          <div className="reveal-up">
            <SimulationResult
              result={simulation}
              onDismiss={() => setSimulation(null)}
              onProvisionAnyway={() => {
                setSimulation(null);
                handleProvision(simulatedIntent);
              }}
            />
          </div>
        )}

        {deploymentResult && (
          <div className="reveal-up">
            <DeploymentResult
              result={deploymentResult}
              onDismiss={() => setDeploymentResult(null)}
              onInspect={setSelectedSliceId}
            />
          </div>
        )}

        <div className="reveal-up reveal-delay-3">
          <ErrorBoundary section="Network topology">
            <TopologyPanel refreshKey={refreshKey} />
          </ErrorBoundary>
        </div>

        <div className="reveal-up reveal-delay-3">
          <SliceFilterBar
            slices={slices}
            filters={filters}
            onChange={setFilters}
            resultCount={visibleSlices.length}
          />
          <ErrorBoundary section="Slice list">
            <SliceDashboard
              slices={visibleSlices}
              loading={loading}
              onDeleteSlice={handleDeleteSlice}
              deletingSliceId={deletingSliceId}
              onSelectSlice={setSelectedSliceId}
              slaEvaluations={slaEvaluations}
            />
          </ErrorBoundary>
          <ErrorBoundary section="Activity feed">
            <ActivityFeed refreshKey={refreshKey} />
          </ErrorBoundary>
        </div>
      </main>

      <ErrorBoundary section="Slice detail">
        <SliceDetailDrawer
          slice={selectedSlice}
          onClose={() => setSelectedSliceId(null)}
          onChanged={() => {
            fetchData();
            fetchTelemetry();
          }}
          onNotify={showToast}
        />
      </ErrorBoundary>

      <footer className="mt-12 border-t border-white/10 bg-black/10">
        <div className="mx-auto max-w-7xl px-4 py-4">
          <p className="text-center font-syne text-sm text-slate-300">
            HELIX - LLM-Powered 5G Network Slice Provisioning
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
