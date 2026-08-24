import { useEffect, useState } from 'react';
import { getTopology } from '../services/api';
import type { NodeUtilization, TopologyView } from '../types/telemetry';

const TYPE_LABELS: Record<string, string> = {
  gnb: 'gNB',
  edge: 'Edge',
  upf: 'UPF',
  core: 'Core',
};

const TYPE_ORDER = ['gnb', 'edge', 'upf', 'core'];

function utilizationColor(percent: number): string {
  if (percent >= 90) return 'bg-rose-400';
  if (percent >= 70) return 'bg-amber-400';
  return 'bg-cyan';
}

function NodeRow({ node, onSelect }: { node: NodeUtilization; onSelect: () => void }) {
  const devicePercent = (node.attached_devices / node.max_devices) * 100;

  return (
    <button
      onClick={onSelect}
      className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5 text-left transition-colors hover:border-cyan/40"
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
            node.health === 'healthy'
              ? 'bg-emerald-400'
              : node.health === 'degraded'
              ? 'bg-amber-400'
              : 'bg-rose-400'
          }`}
        />
        <span className="min-w-0 flex-1 truncate font-syne text-sm text-white">{node.name}</span>
        <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-300">
          {TYPE_LABELS[node.node_type] ?? node.node_type}
        </span>
      </div>

      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full transition-all ${utilizationColor(node.utilization_percent)}`}
          style={{ width: `${Math.min(100, node.utilization_percent)}%` }}
        />
      </div>

      <div className="mt-1.5 flex items-center justify-between font-mono text-[11px] text-slate-400">
        <span>
          {node.allocated_mbps.toFixed(0)} / {node.capacity_mbps.toFixed(0)} Mbps
        </span>
        <span>
          {node.hosted_slices}/{node.max_slices} slices · {devicePercent.toFixed(0)}% devices
        </span>
      </div>
    </button>
  );
}

interface TopologyPanelProps {
  /** Bumped by the parent whenever slices change, to trigger a refresh. */
  refreshKey: number;
  onSelectNode?: (nodeId: string) => void;
}

export function TopologyPanel({ refreshKey, onSelectNode }: TopologyPanelProps) {
  const [topology, setTopology] = useState<TopologyView | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTopology()
      .then((view) => {
        if (!cancelled) {
          setTopology(view);
          setError(null);
        }
      })
      .catch((cause) => {
        if (!cancelled) setError(cause instanceof Error ? cause.message : 'Unavailable');
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (error) {
    return (
      <section className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-slate-400">
        Topology unavailable: {error}
      </section>
    );
  }

  if (!topology) {
    return <div className="mb-6 h-24 animate-pulse rounded-2xl border border-white/10 bg-white/[0.03]" />;
  }

  const utilization =
    topology.total_capacity_mbps > 0
      ? (topology.total_allocated_mbps / topology.total_capacity_mbps) * 100
      : 0;

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    nodes: topology.nodes.filter((node) => node.node_type === type),
  })).filter((group) => group.nodes.length > 0);

  return (
    <section className="mb-6 rounded-2xl border border-white/10 bg-white/[0.03]">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-3">
          <h2 className="font-syne text-sm text-slate-100">Network topology</h2>
          <span className="font-mono text-[11px] text-slate-400">
            {topology.nodes.length} nodes · {topology.total_allocated_mbps.toFixed(0)} /{' '}
            {topology.total_capacity_mbps.toFixed(0)} Mbps ({utilization.toFixed(0)}%)
          </span>
          {topology.saturated_nodes.length > 0 && (
            <span className="rounded bg-rose-400/20 px-1.5 py-0.5 font-mono text-[10px] text-rose-200">
              {topology.saturated_nodes.length} saturated
            </span>
          )}
        </div>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? '' : 'rotate-180'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {!collapsed && (
        <div className="space-y-4 border-t border-white/10 px-4 py-3">
          {grouped.map((group) => (
            <div key={group.type}>
              <h3 className="mb-2 font-syne text-[11px] uppercase tracking-[0.14em] text-slate-400">
                {TYPE_LABELS[group.type] ?? group.type}
              </h3>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {group.nodes.map((node) => (
                  <NodeRow
                    key={node.node_id}
                    node={node}
                    onSelect={() => onSelectNode?.(node.node_id)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
