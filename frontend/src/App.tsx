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
    <div className="min-h-screen bg-navy-900 text-gray-100">
      {/* Header */}
      <header className="border-b border-navy-700 bg-navy-800/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-cyan-500 rounded-lg flex items-center justify-center">
                <svg className="w-6 h-6 text-navy-900" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-100">HELIX</h1>
                <p className="text-xs text-gray-500">5G Intent-Based Network Slicing</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse"></span>
              <span className="text-sm text-gray-400">Connected</span>
            </div>
          </div>
        </div>
      </header>

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed top-20 right-4 z-50 px-4 py-3 rounded-lg shadow-lg transition-all ${
            toast.type === 'success'
              ? 'bg-success/20 border border-success/30 text-success'
              : toast.type === 'error'
              ? 'bg-danger/20 border border-danger/30 text-danger'
              : 'bg-yellow-500/20 border border-yellow-500/30 text-yellow-400'
          }`}
        >
          <div className="flex items-center gap-2">
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
              className="ml-2 text-current opacity-70 hover:opacity-100"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
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
      <footer className="border-t border-navy-700 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <p className="text-center text-gray-600 text-sm">
            HELIX - LLM-Powered 5G Network Slice Provisioning
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
