import type { SliceConfig } from '../types/slice';
import { SST_NAMES, SST_DESCRIPTIONS } from '../types/slice';

interface SliceCardProps {
  slice: SliceConfig;
  onDelete: (sliceId: string) => void;
  deleting: boolean;
}

export function SliceCard({ slice, onDelete, deleting }: SliceCardProps) {
  const isActive = slice.status === 'active';
  const isConflict = slice.status === 'conflict';

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getUseCaseBadgeColor = (useCase: string) => {
    const colors: Record<string, string> = {
      healthcare: 'bg-red-500/20 text-red-400 border-red-500/30',
      'autonomous-vehicles': 'bg-purple-500/20 text-purple-400 border-purple-500/30',
      iot: 'bg-green-500/20 text-green-400 border-green-500/30',
      broadband: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      gaming: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      industrial: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    };
    return colors[useCase] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  };

  return (
    <div className="bg-navy-800 border border-navy-600 rounded-lg p-4 hover:border-navy-500 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`w-2 h-2 rounded-full ${
                isActive ? 'bg-success' : isConflict ? 'bg-danger' : 'bg-yellow-400'
              }`}
            />
            <h3 className="text-gray-100 font-medium truncate">{slice.name}</h3>
          </div>
          <span
            className={`inline-block text-xs px-2 py-0.5 rounded border ${getUseCaseBadgeColor(
              slice.use_case
            )}`}
          >
            {slice.use_case}
          </span>
        </div>
        <button
          onClick={() => onDelete(slice.slice_id)}
          disabled={deleting}
          className="text-gray-500 hover:text-danger transition-colors p-1 disabled:opacity-50"
          title="Delete slice"
        >
          {deleting ? (
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          )}
        </button>
      </div>

      {/* Technical Details Grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div>
          <span className="text-gray-500">S-NSSAI:</span>
          <span className="ml-2 text-cyan-400 font-mono">
            SST={slice.sst} ({SST_NAMES[slice.sst]})
          </span>
        </div>
        <div>
          <span className="text-gray-500">SD:</span>
          <span className="ml-2 text-cyan-400 font-mono">{slice.sd}</span>
        </div>
        <div>
          <span className="text-gray-500">5QI:</span>
          <span className="ml-2 text-cyan-400 font-mono">{slice.qos_5qi}</span>
        </div>
        <div>
          <span className="text-gray-500">ARP:</span>
          <span className="ml-2 text-cyan-400 font-mono">{slice.arp_priority}</span>
        </div>
        <div>
          <span className="text-gray-500">GBR:</span>
          <span className="ml-2 text-success font-mono">{slice.guaranteed_bitrate_mbps} Mbps</span>
        </div>
        <div>
          <span className="text-gray-500">Max:</span>
          <span className="ml-2 text-gray-300 font-mono">{slice.max_bitrate_mbps} Mbps</span>
        </div>
        <div>
          <span className="text-gray-500">Latency:</span>
          <span className="ml-2 text-gray-300 font-mono">{slice.latency_ms} ms</span>
        </div>
        <div>
          <span className="text-gray-500">Devices:</span>
          <span className="ml-2 text-gray-300 font-mono">{slice.device_count.toLocaleString()}</span>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-navy-600 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-3">
          <span className="capitalize">{slice.security_level}</span>
          <span className="capitalize">{slice.isolation}</span>
          <span>{slice.location}</span>
        </div>
        <span>{formatDate(slice.created_at)}</span>
      </div>
    </div>
  );
}
