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
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-navy-800 border border-navy-600 rounded-lg p-4 animate-pulse"
          >
            <div className="h-6 bg-navy-600 rounded w-3/4 mb-3"></div>
            <div className="h-4 bg-navy-600 rounded w-1/4 mb-4"></div>
            <div className="space-y-2">
              {[1, 2, 3, 4].map((j) => (
                <div key={j} className="h-4 bg-navy-600 rounded"></div>
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (slices.length === 0) {
    return (
      <div className="bg-navy-800 border border-navy-600 rounded-lg p-8 text-center">
        <div className="text-gray-500 mb-2">No slices deployed</div>
        <div className="text-gray-600 text-sm">
          Use the intent input above to provision your first network slice
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium text-gray-200 mb-4">
        Active Network Slices
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
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
