import { useState, useEffect, useCallback } from 'react';
import type { SliceConfig, SliceDeploymentResult, SliceStats, WebSocketMessage } from './types/slice';
import { StatsBar } from './components/StatsBar';
import { IntentInput } from './components/IntentInput';
import { SliceDashboard } from './components/SliceDashboard';
import { DeploymentResult } from './components/DeploymentResult';
import { provisionSlice, getAllSlices, deleteSlice, getSliceStats } from './services/api';
import { websocketService } from './services/websocket';

function App() {
  const [slices, setSlices] = useState<SliceConfig[]>([]);
  const [stats, setStats] = useState<SliceStats | null>(null);
  const [deploymentResult, setDeploymentResult] = useState<SliceDeploymentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [provisioning, setProvisioning] = useState(false);
  const [deletingSliceId, setDeletingSliceId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  // Fetch initial data
  const fetchData = useCallback(async () => {
    try {
      const [slicesData, statsData] = await Promise.all([
        getAllSlices(),
        getSliceStats(),
      ]);
      setSlices(slicesData);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      showToast('Failed to connect to backend', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  // Show toast notification
  const showToast = (message: string, type: 'success' | 'error' | 'warning') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    switch (message.event) {
      case 'slice_created':
        setSlices((prev) => [...prev, message.data as unknown as SliceConfig]);
        getSliceStats().then(setStats);
        break;
      case 'slice_deleted':
        setSlices((prev) =>
          prev.filter((s) => s.slice_id !== (message.data as { slice_id: string }).slice_id)
        );
        getSliceStats().then(setStats);
        break;
      case 'conflict_detected':
        showToast(
          `Conflict detected: ${(message.data as { conflict_type: string }).conflict_type}`,
          'warning'
        );
        break;
    }
  }, []);

  // Initialize WebSocket and fetch data
  useEffect(() => {
    fetchData();
    websocketService.connect();
    const unsubscribe = websocketService.subscribe('all', handleWebSocketMessage);

    return () => {
      unsubscribe();
      websocketService.disconnect();
    };
  }, [fetchData, handleWebSocketMessage]);

  // Handle provision slice
  const handleProvision = async (intent: string) => {
    setProvisioning(true);
    setDeploymentResult(null);

    try {
      const result = await provisionSlice(intent);
      setDeploymentResult(result);

      if (result.success) {
        showToast('Slice deployed successfully', 'success');
        // Refresh data to ensure consistency
        fetchData();
      } else {
        showToast('Slice provisioning failed', 'error');
      }
    } catch (error) {
      console.error('Provision error:', error);
      showToast(
        error instanceof Error ? error.message : 'Failed to provision slice',
        'error'
      );
    } finally {
      setProvisioning(false);
    }
  };

  // Handle delete slice
  const handleDeleteSlice = async (sliceId: string) => {
    setDeletingSliceId(sliceId);

    try {
      await deleteSlice(sliceId);
      showToast('Slice deleted successfully', 'success');
      // Refresh data to ensure consistency
      fetchData();
    } catch (error) {
      console.error('Delete error:', error);
      showToast(
        error instanceof Error ? error.message : 'Failed to delete slice',
        'error'
      );
    } finally {
      setDeletingSliceId(null);
    }
  };

  return (
    <div className="helix-app min-h-screen text-primary relative overflow-x-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/3 h-72 w-72 rounded-full bg-cyan/15 blur-3xl" />
        <div className="absolute top-64 -left-20 h-80 w-80 rounded-full bg-sky-500/15 blur-3xl" />
        <div className="absolute bottom-20 right-0 h-96 w-96 rounded-full bg-emerald-400/10 blur-3xl" />
      </div>
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0b1225]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 bg-gradient-to-br from-cyan-300 via-cyan to-cyan-600 rounded-xl flex items-center justify-center ring-1 ring-cyan/70 shadow-[0_0_20px_rgba(0,212,255,0.35)]">
                <svg className="w-6 h-6 text-background" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-syne font-bold text-white tracking-wide">HELIX</h1>
                <div className="flex items-center gap-2">
                  <p className="text-xs text-slate-300">5G Intent-Based Network Slicing</p>
                  <span className="text-[10px] uppercase tracking-[0.12em] text-cyan border border-cyan/50 rounded px-1.5 py-0.5 bg-cyan/10">
                    Orchestrator
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success pulse-dot"></span>
              <span className="text-sm text-slate-200 font-syne">Connected</span>
            </div>
          </div>
        </div>
      </header>

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-20 right-4 z-50 px-4 py-3 rounded-xl shadow-2xl transition-all backdrop-blur-xl ${
            toast.type === 'success'
              ? 'bg-emerald-400/15 border border-emerald-300/40 text-emerald-200'
              : toast.type === 'error'
              ? 'bg-rose-400/15 border border-rose-300/40 text-rose-200'
              : 'bg-amber-300/20 border border-amber-200/40 text-amber-100'
          }`}
        >
          <div className="flex items-center gap-2 font-syne">
            {toast.type === 'success' && (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            )}
            {toast.type === 'error' && (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            )}
            {toast.type === 'warning' && (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            )}
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="ml-2 text-current opacity-70 hover:opacity-100 transition-opacity"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 md:py-10 relative z-10">
        <section className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 backdrop-blur-sm">
          <p className="text-[11px] uppercase tracking-[0.18em] text-cyan/80 font-semibold">Operational Visibility</p>
          <h2 className="text-slate-100 text-lg md:text-xl font-syne">Intent to deployment, in one control plane.</h2>
        </section>
        <StatsBar stats={stats} loading={loading} />

        <IntentInput onSubmit={handleProvision} loading={provisioning} />

        {deploymentResult && (
          <DeploymentResult
            result={deploymentResult}
            onDismiss={() => setDeploymentResult(null)}
          />
        )}

        <SliceDashboard
          slices={slices}
          loading={loading}
          onDeleteSlice={handleDeleteSlice}
          deletingSliceId={deletingSliceId}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 mt-12 bg-black/10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <p className="text-center text-slate-300 text-sm font-syne">
            HELIX - LLM-Powered 5G Network Slice Provisioning
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
