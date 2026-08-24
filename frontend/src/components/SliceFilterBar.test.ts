// Tests for applyFilters: the pure filter/sort function driving the slice
// list, tested in isolation from the React component it renders inside.

import { describe, expect, it } from 'vitest';
import { applyFilters, DEFAULT_FILTERS, type SliceFilters } from './SliceFilterBar';
import type { SliceConfig } from '../types/slice';

function makeSlice(overrides: Partial<SliceConfig> = {}): SliceConfig {
  return {
    slice_id: 'id-1',
    name: 'Test Slice',
    sst: 1,
    sd: '0x000001',
    qos_5qi: 9,
    arp_priority: 5,
    guaranteed_bitrate_mbps: 50,
    max_bitrate_mbps: 100,
    latency_ms: 20,
    security_level: 'standard',
    isolation: 'shared',
    device_count: 100,
    use_case: 'broadband',
    location: 'Mumbai',
    status: 'active',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

const filters = (overrides: Partial<SliceFilters> = {}): SliceFilters => ({
  ...DEFAULT_FILTERS,
  ...overrides,
});

describe('applyFilters', () => {
  describe('search', () => {
    it('matches by name case-insensitively', () => {
      const slices = [makeSlice({ name: 'Apollo Hospital Slice' })];
      expect(applyFilters(slices, filters({ search: 'apollo' }))).toHaveLength(1);
      expect(applyFilters(slices, filters({ search: 'NOTHERE' }))).toHaveLength(0);
    });

    it('matches by location, use case, SD and 5QI', () => {
      const slice = makeSlice({ location: 'Chennai', use_case: 'healthcare', sd: '0x00abcd', qos_5qi: 69 });
      expect(applyFilters([slice], filters({ search: 'chennai' }))).toHaveLength(1);
      expect(applyFilters([slice], filters({ search: 'healthcare' }))).toHaveLength(1);
      expect(applyFilters([slice], filters({ search: 'abcd' }))).toHaveLength(1);
      expect(applyFilters([slice], filters({ search: '69' }))).toHaveLength(1);
    });

    it('an empty search matches everything', () => {
      const slices = [makeSlice(), makeSlice({ slice_id: 'id-2' })];
      expect(applyFilters(slices, filters({ search: '' }))).toHaveLength(2);
    });

    it('trims surrounding whitespace before matching', () => {
      const slice = makeSlice({ name: 'Padded Name' });
      expect(applyFilters([slice], filters({ search: '  padded  ' }))).toHaveLength(1);
    });
  });

  describe('exact filters', () => {
    it('filters by sst', () => {
      const slices = [makeSlice({ sst: 1 }), makeSlice({ slice_id: 'id-2', sst: 2 })];
      expect(applyFilters(slices, filters({ sst: 2 }))).toHaveLength(1);
    });

    it('filters by status', () => {
      const slices = [makeSlice({ status: 'active' }), makeSlice({ slice_id: 'id-2', status: 'conflict' })];
      expect(applyFilters(slices, filters({ status: 'conflict' }))).toHaveLength(1);
    });

    it('combines multiple filters with AND semantics', () => {
      const slices = [
        makeSlice({ sst: 2, location: 'Chennai' }),
        makeSlice({ slice_id: 'id-2', sst: 2, location: 'Mumbai' }),
      ];
      const result = applyFilters(slices, filters({ sst: 2, location: 'Chennai' }));
      expect(result).toHaveLength(1);
      expect(result[0].location).toBe('Chennai');
    });

    it('null filter values do not narrow the result', () => {
      const slices = [makeSlice(), makeSlice({ slice_id: 'id-2' })];
      expect(applyFilters(slices, filters({ sst: null, status: null }))).toHaveLength(2);
    });
  });

  describe('sorting', () => {
    it('newest first by default (created_at descending)', () => {
      const older = makeSlice({ slice_id: 'a', created_at: '2024-01-01T00:00:00Z' });
      const newer = makeSlice({ slice_id: 'b', created_at: '2024-06-01T00:00:00Z' });
      const result = applyFilters([older, newer], filters({ sort: 'newest' }));
      expect(result.map((s) => s.slice_id)).toEqual(['b', 'a']);
    });

    it('oldest sorts created_at ascending', () => {
      const older = makeSlice({ slice_id: 'a', created_at: '2024-01-01T00:00:00Z' });
      const newer = makeSlice({ slice_id: 'b', created_at: '2024-06-01T00:00:00Z' });
      const result = applyFilters([newer, older], filters({ sort: 'oldest' }));
      expect(result.map((s) => s.slice_id)).toEqual(['a', 'b']);
    });

    it('bandwidth sorts guaranteed_bitrate_mbps descending', () => {
      const small = makeSlice({ slice_id: 'a', guaranteed_bitrate_mbps: 10 });
      const big = makeSlice({ slice_id: 'b', guaranteed_bitrate_mbps: 500 });
      const result = applyFilters([small, big], filters({ sort: 'bandwidth' }));
      expect(result.map((s) => s.slice_id)).toEqual(['b', 'a']);
    });

    it('latency sorts ascending (tightest first)', () => {
      const loose = makeSlice({ slice_id: 'a', latency_ms: 100 });
      const tight = makeSlice({ slice_id: 'b', latency_ms: 5 });
      const result = applyFilters([loose, tight], filters({ sort: 'latency' }));
      expect(result.map((s) => s.slice_id)).toEqual(['b', 'a']);
    });

    it('devices sorts device_count descending', () => {
      const few = makeSlice({ slice_id: 'a', device_count: 10 });
      const many = makeSlice({ slice_id: 'b', device_count: 5000 });
      const result = applyFilters([few, many], filters({ sort: 'devices' }));
      expect(result.map((s) => s.slice_id)).toEqual(['b', 'a']);
    });

    it('name sorts alphabetically', () => {
      const zebra = makeSlice({ slice_id: 'a', name: 'Zebra' });
      const apple = makeSlice({ slice_id: 'b', name: 'Apple' });
      const result = applyFilters([zebra, apple], filters({ sort: 'name' }));
      expect(result.map((s) => s.slice_id)).toEqual(['b', 'a']);
    });
  });

  describe('immutability', () => {
    it('does not mutate the input array', () => {
      const slices = [makeSlice({ slice_id: 'a' }), makeSlice({ slice_id: 'b' })];
      const original = [...slices];
      applyFilters(slices, filters({ sort: 'name' }));
      expect(slices).toEqual(original);
    });
  });
});
