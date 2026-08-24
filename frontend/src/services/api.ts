// Typed client for the HELIX API.

import { API_BASE_URL } from '../config';
import type {
  SliceBreakdown,
  SliceConfig,
  SliceDeploymentResult,
  SliceSimulationResult,
  SliceStats,
} from '../types/slice';
import type {
  AuditEvent,
  ExportFormat,
  NetworkKpiSummary,
  ParserStatus,
  PlacementDecision,
  SlaEvaluation,
  SlaTarget,
  TelemetrySnapshot,
  TopologyView,
} from '../types/telemetry';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }

  /** True when retrying later could plausibly succeed. */
  get isTransient(): boolean {
    return this.status === 429 || this.status >= 500;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail || 'Request failed');
  }
  return response.json() as Promise<T>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
    return await handleResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    // A network-level failure is indistinguishable from the backend being down;
    // surface it as a 0 so callers can treat it as "unreachable".
    throw new ApiError(0, error instanceof Error ? error.message : 'Network error');
  }
}

function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : '';
}

// --- Slices ------------------------------------------------------------------

export function provisionSlice(intent: string): Promise<SliceDeploymentResult> {
  return request('/api/slices/provision', {
    method: 'POST',
    body: JSON.stringify({ intent }),
  });
}

export function simulateSlice(
  intent: string,
  applyRemediation = true,
): Promise<SliceSimulationResult> {
  return request('/api/slices/simulate', {
    method: 'POST',
    body: JSON.stringify({ intent, apply_remediation: applyRemediation }),
  });
}

export function getAllSlices(filters: {
  use_case?: string;
  location?: string;
  status?: string;
} = {}): Promise<SliceConfig[]> {
  return request(`/api/slices${query(filters)}`);
}

export function getSlice(sliceId: string): Promise<SliceConfig> {
  return request(`/api/slices/${sliceId}`);
}

export function updateSlice(
  sliceId: string,
  changes: Partial<SliceConfig>,
): Promise<SliceConfig> {
  return request(`/api/slices/${sliceId}`, {
    method: 'PATCH',
    body: JSON.stringify(changes),
  });
}

export function scaleSlice(sliceId: string, factor: number): Promise<SliceConfig> {
  return request(`/api/slices/${sliceId}/scale`, {
    method: 'POST',
    body: JSON.stringify({ factor }),
  });
}

export function suspendSlice(sliceId: string): Promise<{ new_status: string; message: string }> {
  return request(`/api/slices/${sliceId}/suspend`, { method: 'POST' });
}

export function resumeSlice(sliceId: string): Promise<{ new_status: string; message: string }> {
  return request(`/api/slices/${sliceId}/resume`, { method: 'POST' });
}

export function deleteSlice(
  sliceId: string,
): Promise<{ message: string; slice_id: string; released_mbps: number }> {
  return request(`/api/slices/${sliceId}`, { method: 'DELETE' });
}

export function getSliceStats(): Promise<SliceStats> {
  return request('/api/slices/stats/summary');
}

export function getSliceBreakdown(): Promise<SliceBreakdown> {
  return request('/api/slices/stats/breakdown');
}

// --- Telemetry and SLA ---------------------------------------------------------

export function getTelemetrySummary(): Promise<NetworkKpiSummary> {
  return request('/api/telemetry/summary');
}

export function getSliceTelemetry(sliceId: string, history = 60): Promise<TelemetrySnapshot> {
  return request(`/api/telemetry/${sliceId}${query({ history })}`);
}

export function getSlaEvaluations(status?: string): Promise<SlaEvaluation[]> {
  return request(`/api/telemetry/sla${query({ status })}`);
}

export function getSlaViolations(): Promise<SlaEvaluation[]> {
  return request('/api/telemetry/violations');
}

export function getSlaTarget(sliceId: string): Promise<SlaTarget> {
  return request(`/api/telemetry/${sliceId}/sla-target`);
}

export function forceTelemetryTick(): Promise<{ sampled_slices: number; ticks: number }> {
  return request('/api/telemetry/tick', { method: 'POST' });
}

// --- Topology --------------------------------------------------------------------

export function getTopology(): Promise<TopologyView> {
  return request('/api/topology');
}

export function getPlacement(sliceId: string): Promise<PlacementDecision> {
  return request(`/api/topology/placement/${sliceId}`);
}

export function rebalanceSlice(sliceId: string): Promise<PlacementDecision> {
  return request(`/api/topology/placement/${sliceId}/rebalance`, { method: 'POST' });
}

export function setNodeHealth(nodeId: string, health: string): Promise<{ health: string }> {
  return request(`/api/topology/nodes/${nodeId}/health${query({ health })}`, { method: 'POST' });
}

// --- Events ----------------------------------------------------------------------

export function getEvents(filters: {
  limit?: number;
  slice_id?: string;
  event_type?: string;
  severity?: string;
} = {}): Promise<AuditEvent[]> {
  return request(`/api/events${query(filters)}`);
}

// --- System and export -------------------------------------------------------------

export function getParserStatus(): Promise<ParserStatus> {
  return request('/api/system/parser');
}

export function getSystemInfo(): Promise<Record<string, unknown>> {
  return request('/api/system/info');
}

export function getExportFormats(): Promise<{ formats: ExportFormat[] }> {
  return request('/api/export/formats');
}

/** URL for downloading a slice (or the whole network) in a given format. */
export function exportUrl(format: string, sliceId?: string): string {
  const path = sliceId ? `/api/export/slices/${sliceId}` : '/api/export/slices';
  return `${API_BASE_URL}${path}${query({ format, download: true })}`;
}

/** Fetch an export as text, for previewing it in the UI. */
export async function fetchExport(format: string, sliceId?: string): Promise<string> {
  const path = sliceId ? `/api/export/slices/${sliceId}` : '/api/export/slices';
  const response = await fetch(`${API_BASE_URL}${path}${query({ format })}`);
  if (!response.ok) {
    throw new ApiError(response.status, `Export failed: ${response.statusText}`);
  }
  return response.text();
}
