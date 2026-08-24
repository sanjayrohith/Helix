// TypeScript types matching backend Pydantic models

export type SecurityLevel = 'standard' | 'high' | 'critical';
export type IsolationType = 'shared' | 'dedicated' | 'strict';
export type SliceStatus = 'pending' | 'active' | 'conflict' | 'rejected';
export type ConflictType =
  | 'bandwidth'
  | 'snssai'
  | 'arp'
  | 'regulatory'
  | 'latency'
  | 'isolation'
  | 'device_density';
export type ConflictSeverity = 'blocking' | 'warning' | 'advisory';
export type WebSocketEvent =
  | 'slice_created'
  | 'slice_updated'
  | 'slice_deleted'
  | 'conflict_detected'
  | 'telemetry'
  | 'sla_alert';

export interface SliceConfig {
  slice_id: string;
  name: string;
  sst: number; // 1=eMBB, 2=URLLC, 3=mMTC
  sd: string; // Slice Differentiator hex
  qos_5qi: number;
  arp_priority: number; // 1 (highest) to 15 (lowest)
  guaranteed_bitrate_mbps: number;
  max_bitrate_mbps: number;
  latency_ms: number;
  security_level: SecurityLevel;
  isolation: IsolationType;
  device_count: number;
  use_case: string;
  location: string;
  status: SliceStatus;
  created_at: string;
  updated_at: string | null;
}

export interface ConflictFinding {
  conflict_type: ConflictType;
  severity: ConflictSeverity;
  details: string;
  suggestions: string[];
  remediation: Partial<Record<keyof SliceConfig, string | number>>;
  conflicting_slice_ids: string[];
}

export interface ConflictReport {
  has_conflict: boolean;
  conflict_type: ConflictType | null;
  details: string;
  suggestions: string[];
  findings: ConflictFinding[];
  auto_remediation: Partial<Record<keyof SliceConfig, string | number>>;
}

export interface SliceDeploymentResult {
  success: boolean;
  slice_config: SliceConfig;
  conflict_report: ConflictReport;
  deploy_time_seconds: number;
  message: string;
  parser_used: string;
  parse_fallback_reason: string | null;
  parse_trace: ParseTrace | null;
  auto_remediated: boolean;
}

export interface ParseTrace {
  matched_profile: string;
  profile_score: number;
  matched_keywords: string[];
  derived: Record<string, string>;
}

export interface SliceSimulationResult {
  would_deploy: boolean;
  slice_config: SliceConfig;
  conflict_report: ConflictReport;
  remediated_config: SliceConfig | null;
  remediated_report: ConflictReport | null;
  parser_used: string;
  capacity_before_mbps: number;
  capacity_after_mbps: number;
}

export interface SliceBreakdown {
  capacity_mbps: number;
  used_mbps: number;
  available_mbps: number;
  by_sst: Record<string, number>;
  by_status: Record<string, number>;
  by_use_case: Record<string, number>;
  by_location: Record<string, number>;
  by_isolation: Record<string, number>;
  total_devices: number;
}

export interface SliceStats {
  total_slices: number;
  active_slices: number;
  total_bandwidth_used_mbps: number;
  bandwidth_remaining_mbps: number;
  conflict_count: number;
}

export interface WebSocketMessage {
  event: WebSocketEvent;
  data: Record<string, unknown>;
}

// SST Type names for display
export const SST_NAMES: Record<number, string> = {
  1: 'eMBB',
  2: 'URLLC',
  3: 'mMTC',
};

// SST descriptions
export const SST_DESCRIPTIONS: Record<number, string> = {
  1: 'Enhanced Mobile Broadband',
  2: 'Ultra-Reliable Low-Latency',
  3: 'Massive Machine Type Comm.',
};
