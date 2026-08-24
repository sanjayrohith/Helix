// Types for live telemetry, SLA compliance, topology and the audit journal.

export type SlaStatus = 'meeting' | 'at_risk' | 'violated' | 'unknown';
export type KpiName =
  | 'throughput'
  | 'latency'
  | 'jitter'
  | 'packet_loss'
  | 'prb_utilization'
  | 'availability';

export interface SliceTelemetry {
  slice_id: string;
  timestamp: string;
  throughput_mbps: number;
  offered_load_mbps: number;
  latency_ms: number;
  jitter_ms: number;
  packet_loss_percent: number;
  prb_utilization_percent: number;
  active_devices: number;
  availability_percent: number;
}

export interface SlaBreach {
  kpi: KpiName;
  observed: number;
  target: number;
  severity: 'warning' | 'critical';
  description: string;
}

export interface SlaEvaluation {
  slice_id: string;
  slice_name: string;
  status: SlaStatus;
  evaluated_at: string;
  compliance_score: number;
  breaches: SlaBreach[];
}

export interface SlaTarget {
  slice_id: string;
  max_latency_ms: number;
  min_throughput_mbps: number;
  max_packet_loss_percent: number;
  max_jitter_ms: number;
  min_availability_percent: number;
}

export interface TelemetrySnapshot {
  slice_id: string;
  slice_name: string;
  latest: SliceTelemetry | null;
  sla: SlaEvaluation | null;
  history: SliceTelemetry[];
}

export interface NetworkKpiSummary {
  sampled_at: string;
  total_throughput_mbps: number;
  mean_latency_ms: number;
  mean_packet_loss_percent: number;
  mean_prb_utilization_percent: number;
  slices_meeting_sla: number;
  slices_at_risk: number;
  slices_violating_sla: number;
}

// --- Topology ---------------------------------------------------------------

export type NodeType = 'gnb' | 'edge' | 'upf' | 'core';
export type NodeHealth = 'healthy' | 'degraded' | 'offline';

export interface NodeUtilization {
  node_id: string;
  name: string;
  node_type: NodeType;
  location: string;
  health: NodeHealth;
  capacity_mbps: number;
  allocated_mbps: number;
  utilization_percent: number;
  hosted_slices: number;
  max_slices: number;
  attached_devices: number;
  max_devices: number;
  slice_ids: string[];
}

export interface NetworkLink {
  link_id: string;
  source: string;
  target: string;
  capacity_mbps: number;
  latency_ms: number;
}

export interface PlacementCandidate {
  node_id: string;
  node_name: string;
  score: number;
  feasible: boolean;
  reasons: string[];
}

export interface PlacementDecision {
  slice_id: string;
  slice_name: string;
  node_id: string | null;
  node_name: string | null;
  placed: boolean;
  explanation: string;
  candidates: PlacementCandidate[];
}

export interface TopologyView {
  nodes: NodeUtilization[];
  links: NetworkLink[];
  placements: Record<string, string>;
  total_capacity_mbps: number;
  total_allocated_mbps: number;
  saturated_nodes: string[];
}

// --- Audit journal -----------------------------------------------------------

export type EventSeverity = 'info' | 'warning' | 'error';

export interface AuditEvent {
  event_id: string;
  event_type: string;
  severity: EventSeverity;
  timestamp: string;
  slice_id: string | null;
  slice_name: string | null;
  actor: string;
  summary: string;
  detail: Record<string, unknown>;
}

// --- System ------------------------------------------------------------------

export interface ParserStatus {
  active_parser: string;
  llm_configured: boolean;
  llm_model: string;
  force_rule_based: boolean;
  fallback_parser: string;
}

export interface ExportFormat {
  id: string;
  label: string;
  media_type: string;
  description: string;
}
