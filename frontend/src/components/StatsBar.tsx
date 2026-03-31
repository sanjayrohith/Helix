import type { SliceStats } from '../types/slice';

interface StatsBarProps {
  stats: SliceStats | null;
  loading: boolean;
}

export function StatsBar({ stats, loading }: StatsBarProps) {
  const bandwidthUsedPercent = stats 
    ? (stats.total_bandwidth_used_mbps / 1000) * 100 
    : 0;

  return (
    <div className="stats-grid grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
      {/* Active Slices */}
      <div className="stat-card reveal-up p-5 stat-card-hover shadow-[0_14px_30px_rgba(8,15,35,0.45)]">
        <div className="flex items-center justify-between mb-2">
          <div className="stat-label mb-0">Active Slices</div>
          <div className="stat-icon-wrap text-cyan">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        </div>
        {loading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-navy-600 rounded w-16 mb-1"></div>
            <div className="h-4 bg-navy-600 rounded w-20"></div>
          </div>
        ) : (
          <>
            <div className="stat-value">
              {stats?.active_slices ?? '-'}
            </div>
            <div className="stat-secondary">
              of {stats?.total_slices ?? '-'} total
            </div>
          </>
        )}
      </div>

      {/* Bandwidth Used */}
      <div className="stat-card reveal-up p-5 stat-card-hover shadow-[0_14px_30px_rgba(8,15,35,0.45)]">
        <div className="flex items-center justify-between mb-2">
          <div className="stat-label mb-0">Bandwidth Used</div>
          <div className="stat-icon-wrap text-cyan">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 12h10m-7 4h4m-8 5h12a2 2 0 002-2V5a2 2 0 00-2-2H6a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
          </div>
        </div>
        {loading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-navy-600 rounded w-16 mb-1"></div>
            <div className="h-4 bg-navy-600 rounded w-20"></div>
          </div>
        ) : (
          <>
            <div className="stat-value">
              {stats ? stats.total_bandwidth_used_mbps.toFixed(0) : '-'}
            </div>
            <div className="stat-secondary">/ 1000 Mbps</div>
            {/* Progress bar */}
            <div className="progress-bar h-1.5 mt-3">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${bandwidthUsedPercent}%` }}
              />
            </div>
          </>
        )}
      </div>

      {/* Bandwidth Available */}
      <div className="stat-card reveal-up p-5 stat-card-hover shadow-[0_14px_30px_rgba(8,15,35,0.45)]">
        <div className="flex items-center justify-between mb-2">
          <div className="stat-label mb-0">Bandwidth Available</div>
          <div className="stat-icon-wrap text-cyan">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
        </div>
        {loading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-navy-600 rounded w-16 mb-1"></div>
            <div className="h-4 bg-navy-600 rounded w-20"></div>
          </div>
        ) : (
          <>
            <div className="stat-value">
              {stats ? stats.bandwidth_remaining_mbps.toFixed(0) : '-'}
            </div>
            <div className="stat-secondary">Mbps</div>
          </>
        )}
      </div>

      {/* Conflicts - Red accent */}
      <div className="stat-card-conflict reveal-up p-5 stat-card-hover shadow-[0_14px_30px_rgba(8,15,35,0.45)]">
        <div className="flex items-center justify-between mb-2">
          <div className="stat-label mb-0">Conflicts</div>
          <div className="stat-icon-wrap text-danger border-danger/30 bg-danger/10">
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
        </div>
        {loading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-navy-600 rounded w-16 mb-1"></div>
            <div className="h-4 bg-navy-600 rounded w-20"></div>
          </div>
        ) : (
          <>
            <div className={`stat-value ${stats && stats.conflict_count > 0 ? 'stat-value-danger' : ''}`}>
              {stats?.conflict_count ?? '-'}
            </div>
            <div className="stat-secondary">detected</div>
          </>
        )}
      </div>
    </div>
  );
}
