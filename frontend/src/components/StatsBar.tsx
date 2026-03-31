import type { SliceStats } from '../types/slice';

interface StatsBarProps {
  stats: SliceStats | null;
  loading: boolean;
}

export function StatsBar({ stats, loading }: StatsBarProps) {
  const statCards = [
    {
      label: 'Active Slices',
      value: stats?.active_slices ?? '-',
      subtext: `of ${stats?.total_slices ?? '-'} total`,
      color: 'text-cyan-400',
    },
    {
      label: 'Bandwidth Used',
      value: stats ? `${stats.total_bandwidth_used_mbps.toFixed(0)}` : '-',
      subtext: '/ 1000 Mbps',
      color: 'text-cyan-400',
    },
    {
      label: 'Bandwidth Available',
      value: stats ? `${stats.bandwidth_remaining_mbps.toFixed(0)}` : '-',
      subtext: 'Mbps',
      color: stats && stats.bandwidth_remaining_mbps < 200 ? 'text-yellow-400' : 'text-success',
    },
    {
      label: 'Conflicts',
      value: stats?.conflict_count ?? '-',
      subtext: 'detected',
      color: stats && stats.conflict_count > 0 ? 'text-danger' : 'text-success',
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {statCards.map((card) => (
        <div
          key={card.label}
          className="bg-navy-800 border border-navy-600 rounded-lg p-4"
        >
          <div className="text-gray-400 text-sm mb-1">{card.label}</div>
          {loading ? (
            <div className="animate-pulse">
              <div className="h-8 bg-navy-600 rounded w-16 mb-1"></div>
              <div className="h-4 bg-navy-600 rounded w-20"></div>
            </div>
          ) : (
            <>
              <div className={`text-2xl font-bold font-mono ${card.color}`}>
                {card.value}
              </div>
              <div className="text-gray-500 text-xs">{card.subtext}</div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
