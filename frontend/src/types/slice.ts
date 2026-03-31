// TypeScript types matching backend Pydantic models

export type SecurityLevel = 'standard' | 'high' | 'critical';
export type IsolationType = 'shared' | 'dedicated' | 'strict';
export type SliceStatus = 'pending' | 'active' | 'conflict' | 'rejected';
export type ConflictType = 'bandwidth' | 'snssai' | 'arp' | 'regulatory';
export type WebSocketEvent = 'slice_created' | 'slice_deleted' | 'conflict_detected';

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
}

export interface ConflictReport {
  has_conflict: boolean;
  conflict_type: ConflictType | null;
  details: string;
  suggestions: string[];
}

export interface SliceDeploymentResult {
  success: boolean;
  slice_config: SliceConfig;
  conflict_report: ConflictReport;
  deploy_time_seconds: number;
  message: string;
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
