import type { SliceConfig } from '../types/slice';
import { SST_NAMES } from '../types/slice';
import type { SlaEvaluation } from '../types/telemetry';
import { SlaBadge } from './SlaBadge';

interface SliceCardProps {
  slice: SliceConfig;
  onDelete: (sliceId: string) => void;
  deleting: boolean;
  onSelect?: (sliceId: string) => void;
  sla?: SlaEvaluation;
}

// SST-based color mapping for top border and badge
const getSSTPalette = (sst: number) => {
  switch (sst) {
    case 1: // eMBB - green
      return {
        border: 'border-t-success',
        badge: 'bg-success/20 text-success border-success/30',
      };
    case 2: // URLLC - cyan
      return {
        border: 'border-t-cyan',
        badge: 'bg-cyan/20 text-cyan border-cyan/30',
      };
    case 3: // mMTC - amber
      return {
        border: 'border-t-amber-400',
        badge: 'bg-amber-400/20 text-amber-400 border-amber-400/30',
      };
    default:
      return {
        border: 'border-t-gray-400',
        badge: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
      };
  }
};

export function SliceCard({ slice, onDelete, deleting, onSelect, sla }: SliceCardProps) {
  const isActive = slice.status === 'active';
  const isConflict = slice.status === 'conflict';
  const sstPalette = getSSTPalette(slice.sst);

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
    <div
      className={`reveal-up bg-white/[0.045] border border-white/10 border-t-2 ${sstPalette.border} rounded-2xl p-5 hover:border-cyan/40 transition-all duration-200 hover:-translate-y-0.5 panel-glow shadow-[0_16px_30px_rgba(5,10,25,0.35)] ${
        onSelect ? 'cursor-pointer' : ''
      }`}
      onClick={() => onSelect?.(slice.slice_id)}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={(event) => {
        if (onSelect && (event.key === 'Enter' || event.key === ' ')) {
          event.preventDefault();
          onSelect(slice.slice_id);
        }
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isActive ? 'bg-success' : isConflict ? 'bg-danger' : 'bg-yellow-400'
              }`}
            />
            <h3 className="text-white font-syne font-semibold truncate">{slice.name}</h3>
          </div>
          <div className="flex items-center gap-2">
            {/* SST Badge Pill */}
            <span className={`inline-block text-xs px-2.5 py-1 rounded-md border font-mono uppercase tracking-wide ${sstPalette.badge}`}>
              {SST_NAMES[slice.sst]}
            </span>
            {/* Use Case Badge */}
            <span
              className={`inline-block text-xs px-2 py-0.5 rounded-md border capitalize ${getUseCaseBadgeColor(
                slice.use_case
              )}`}
            >
              {slice.use_case}
            </span>
            {sla && <SlaBadge status={sla.status} score={sla.compliance_score} compact />}
          </div>
        </div>
        <button
          onClick={(event) => {
            // The card itself opens the drawer; deleting must not do both.
            event.stopPropagation();
            onDelete(slice.slice_id);
          }}
          disabled={deleting}
          className="text-slate-400 hover:text-danger transition-colors p-1 disabled:opacity-50"
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
          <span className="text-slate-400 font-syne">S-NSSAI:</span>
          <span className="ml-2 text-cyan font-mono">
            SST={slice.sst}
          </span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">SD:</span>
          <span className="ml-2 text-cyan font-mono">{slice.sd}</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">5QI:</span>
          <span className="ml-2 text-cyan font-mono">{slice.qos_5qi}</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">ARP:</span>
          <span className="ml-2 text-cyan font-mono">{slice.arp_priority}</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">GBR:</span>
          <span className="ml-2 text-success font-mono">{slice.guaranteed_bitrate_mbps} Mbps</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">Max:</span>
          <span className="ml-2 text-slate-100 font-mono">{slice.max_bitrate_mbps} Mbps</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">Latency:</span>
          <span className="ml-2 text-slate-100 font-mono">{slice.latency_ms} ms</span>
        </div>
        <div>
          <span className="text-slate-400 font-syne">Devices:</span>
          <span className="ml-2 text-slate-100 font-mono">{slice.device_count.toLocaleString()}</span>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between text-xs text-slate-300">
        <div className="flex items-center gap-3 font-syne">
          <span className="capitalize">{slice.security_level}</span>
          <span className="capitalize">{slice.isolation}</span>
          <span>{slice.location}</span>
        </div>
        <span className="font-mono">{formatDate(slice.created_at)}</span>
      </div>
    </div>
  );
}
