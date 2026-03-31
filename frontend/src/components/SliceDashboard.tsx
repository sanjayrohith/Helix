import type { SliceConfig } from '../types/slice';
import { SliceCard } from './SliceCard';

interface SliceDashboardProps {
  slices: SliceConfig[];
  loading: boolean;
  onDeleteSlice: (sliceId: string) => void;
  deletingSliceId: string | null;
}

export function SliceDashboard({
  slices,
  loading,
  onDeleteSlice,
  deletingSliceId,
}: SliceDashboardProps) {
  if (loading) {
    return (
      <div className="slice-grid grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="reveal-up bg-white/[0.04] border border-white/10 rounded-2xl p-5 animate-pulse"
          >
            <div className="h-6 bg-slate-700/60 rounded w-3/4 mb-3"></div>
            <div className="h-4 bg-slate-700/60 rounded w-1/4 mb-4"></div>
            <div className="space-y-2">
              {[1, 2, 3, 4].map((j) => (
                <div key={j} className="h-4 bg-slate-700/60 rounded"></div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (slices.length === 0) {
    return (
      <div className="reveal-up bg-white/[0.04] border border-white/10 rounded-2xl p-12 text-center panel-glow">
        {/* Hexagon SVG Icon */}
        <div className="flex justify-center mb-4">
          <svg
            className="w-16 h-16 text-slate-400 opacity-70"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 3v3m0 12v3m9-9h-3M6 12H3m15.364-6.364l-2.121 2.121M8.757 15.243l-2.121 2.121m12.728 0l-2.121-2.121M8.757 8.757L6.636 6.636"
            />
            {/* Hexagon shape */}
            <polygon
              points="12,2 20,7 20,17 12,22 4,17 4,7"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <div className="text-white font-syne text-lg mb-2">No slices deployed</div>
        <div className="text-slate-300 text-sm max-w-md mx-auto">
          Use the intent input above to provision your first network slice using natural language
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-syne font-semibold text-white tracking-wide">
          Active Network Slices
        </h2>
        <span className="text-xs font-mono text-cyan border border-cyan/40 bg-cyan/10 rounded-md px-2 py-1">
          {slices.length} live
        </span>
      </div>
      <div className="slice-grid grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {slices.map((slice) => (
          <SliceCard
            key={slice.slice_id}
            slice={slice}
            onDelete={onDeleteSlice}
            deleting={deletingSliceId === slice.slice_id}
          />
        ))}
      </div>
    </div>
  );
}
