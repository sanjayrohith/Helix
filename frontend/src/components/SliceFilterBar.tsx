import { useMemo } from 'react';
import type { SliceConfig } from '../types/slice';
import { SST_NAMES } from '../types/slice';

export interface SliceFilters {
  search: string;
  sst: number | null;
  status: string | null;
  useCase: string | null;
  location: string | null;
  sort: SortKey;
}

export type SortKey = 'newest' | 'oldest' | 'bandwidth' | 'latency' | 'name' | 'devices';

export const DEFAULT_FILTERS: SliceFilters = {
  search: '',
  sst: null,
  status: null,
  useCase: null,
  location: null,
  sort: 'newest',
};

const SORTS: { id: SortKey; label: string }[] = [
  { id: 'newest', label: 'Newest' },
  { id: 'oldest', label: 'Oldest' },
  { id: 'bandwidth', label: 'Bandwidth' },
  { id: 'latency', label: 'Latency' },
  { id: 'devices', label: 'Devices' },
  { id: 'name', label: 'Name' },
];

/** Apply the active filters and sort to a slice list. */
export function applyFilters(slices: SliceConfig[], filters: SliceFilters): SliceConfig[] {
  const term = filters.search.trim().toLowerCase();

  const filtered = slices.filter((slice) => {
    if (filters.sst !== null && slice.sst !== filters.sst) return false;
    if (filters.status && slice.status !== filters.status) return false;
    if (filters.useCase && slice.use_case !== filters.useCase) return false;
    if (filters.location && slice.location !== filters.location) return false;
    if (!term) return true;
    // Search across the fields an operator would actually recall.
    return [slice.name, slice.use_case, slice.location, slice.sd, String(slice.qos_5qi)]
      .join(' ')
      .toLowerCase()
      .includes(term);
  });

  const sorted = [...filtered];
  switch (filters.sort) {
    case 'oldest':
      sorted.sort((a, b) => a.created_at.localeCompare(b.created_at));
      break;
    case 'bandwidth':
      sorted.sort((a, b) => b.guaranteed_bitrate_mbps - a.guaranteed_bitrate_mbps);
      break;
    case 'latency':
      sorted.sort((a, b) => a.latency_ms - b.latency_ms);
      break;
    case 'devices':
      sorted.sort((a, b) => b.device_count - a.device_count);
      break;
    case 'name':
      sorted.sort((a, b) => a.name.localeCompare(b.name));
      break;
    default:
      sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
  }
  return sorted;
}

interface SliceFilterBarProps {
  slices: SliceConfig[];
  filters: SliceFilters;
  onChange: (filters: SliceFilters) => void;
  resultCount: number;
}

export function SliceFilterBar({
  slices,
  filters,
  onChange,
  resultCount,
}: SliceFilterBarProps) {
  const useCases = useMemo(
    () => [...new Set(slices.map((slice) => slice.use_case))].sort(),
    [slices],
  );
  const locations = useMemo(
    () => [...new Set(slices.map((slice) => slice.location))].sort(),
    [slices],
  );

  const set = <K extends keyof SliceFilters>(key: K, value: SliceFilters[K]) =>
    onChange({ ...filters, [key]: value });

  const active =
    filters.search !== '' ||
    filters.sst !== null ||
    filters.status !== null ||
    filters.useCase !== null ||
    filters.location !== null;

  const selectClass =
    'rounded-lg border border-white/10 bg-white/[0.04] px-2 py-1.5 font-syne text-xs text-slate-200 outline-none focus:border-cyan/40';

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <div className="relative min-w-[200px] flex-1">
        <svg
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z"
          />
        </svg>
        <input
          value={filters.search}
          onChange={(event) => set('search', event.target.value)}
          placeholder="Search by name, use case, location, SD or 5QI"
          className="w-full rounded-lg border border-white/10 bg-white/[0.04] py-1.5 pl-9 pr-3 font-syne text-xs text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan/40"
        />
      </div>

      <select
        value={filters.sst ?? ''}
        onChange={(event) => set('sst', event.target.value ? Number(event.target.value) : null)}
        className={selectClass}
      >
        <option value="">All types</option>
        {[1, 2, 3].map((sst) => (
          <option key={sst} value={sst}>
            {SST_NAMES[sst]}
          </option>
        ))}
      </select>

      <select
        value={filters.status ?? ''}
        onChange={(event) => set('status', event.target.value || null)}
        className={selectClass}
      >
        <option value="">All statuses</option>
        {['active', 'pending', 'conflict', 'rejected'].map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>

      {useCases.length > 1 && (
        <select
          value={filters.useCase ?? ''}
          onChange={(event) => set('useCase', event.target.value || null)}
          className={selectClass}
        >
          <option value="">All use cases</option>
          {useCases.map((useCase) => (
            <option key={useCase} value={useCase}>
              {useCase}
            </option>
          ))}
        </select>
      )}

      {locations.length > 1 && (
        <select
          value={filters.location ?? ''}
          onChange={(event) => set('location', event.target.value || null)}
          className={selectClass}
        >
          <option value="">All locations</option>
          {locations.map((location) => (
            <option key={location} value={location}>
              {location}
            </option>
          ))}
        </select>
      )}

      <select
        value={filters.sort}
        onChange={(event) => set('sort', event.target.value as SortKey)}
        className={selectClass}
      >
        {SORTS.map((sort) => (
          <option key={sort.id} value={sort.id}>
            Sort: {sort.label}
          </option>
        ))}
      </select>

      <span className="font-mono text-[11px] text-slate-400">
        {resultCount} of {slices.length}
      </span>

      {active && (
        <button
          onClick={() => onChange({ ...DEFAULT_FILTERS, sort: filters.sort })}
          className="rounded-lg border border-white/10 px-2 py-1 font-syne text-[11px] text-slate-300 hover:text-white"
        >
          Clear
        </button>
      )}
    </div>
  );
}
