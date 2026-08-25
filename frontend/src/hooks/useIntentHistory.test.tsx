// Tests useIntentHistory against jsdom's real localStorage, and separately
// verifies it survives storage being unavailable entirely - the case that
// actually motivated the hook's try/catch (a private window, blocked site
// data, or a browser that throws on storage access).

import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useIntentHistory } from './useIntentHistory';

const STORAGE_KEY = 'helix.intentHistory';

describe('useIntentHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('starts empty with nothing stored', () => {
    const { result } = renderHook(() => useIntentHistory());
    expect(result.current.history).toEqual([]);
  });

  it('loads previously stored entries on mount', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ intent: 'existing', at: '2024-01-01T00:00:00Z', succeeded: true }]),
    );
    const { result } = renderHook(() => useIntentHistory());
    expect(result.current.history).toHaveLength(1);
    expect(result.current.history[0].intent).toBe('existing');
  });

  it('record() prepends a new entry', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => result.current.record('first intent', true));
    act(() => result.current.record('second intent', false));

    expect(result.current.history.map((e) => e.intent)).toEqual([
      'second intent',
      'first intent',
    ]);
    expect(result.current.history[0].succeeded).toBe(false);
  });

  it('record() persists to localStorage', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => result.current.record('persisted intent', true));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]');
    expect(stored).toHaveLength(1);
    expect(stored[0].intent).toBe('persisted intent');
  });

  it('re-recording the same intent moves it to the front instead of duplicating', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => result.current.record('repeat me', false));
    act(() => result.current.record('other intent', true));
    act(() => result.current.record('repeat me', true));

    expect(result.current.history).toHaveLength(2);
    expect(result.current.history[0]).toMatchObject({ intent: 'repeat me', succeeded: true });
  });

  it('ignores a blank intent', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => result.current.record('   ', true));
    expect(result.current.history).toEqual([]);
  });

  it('caps history at 15 entries', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => {
      for (let i = 0; i < 20; i += 1) {
        result.current.record(`intent ${i}`, true);
      }
    });
    expect(result.current.history).toHaveLength(15);
    // Most recent 15 survive; the oldest are dropped.
    expect(result.current.history[0].intent).toBe('intent 19');
  });

  it('clear() empties both state and storage', () => {
    const { result } = renderHook(() => useIntentHistory());
    act(() => result.current.record('to be cleared', true));
    act(() => result.current.clear());

    expect(result.current.history).toEqual([]);
    expect(localStorage.getItem(STORAGE_KEY)).toBe('[]');
  });

  it('malformed JSON in storage is treated as empty history, not a crash', () => {
    localStorage.setItem(STORAGE_KEY, '{not valid json');
    const { result } = renderHook(() => useIntentHistory());
    expect(result.current.history).toEqual([]);
  });

  it('a non-array value in storage is treated as empty history', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ not: 'an array' }));
    const { result } = renderHook(() => useIntentHistory());
    expect(result.current.history).toEqual([]);
  });
});

describe('useIntentHistory when storage is unavailable', () => {
  it('record() does not throw when localStorage.setItem throws', () => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = vi.fn(() => {
      throw new DOMException('blocked');
    });

    try {
      const { result } = renderHook(() => useIntentHistory());
      expect(() => act(() => result.current.record('intent', true))).not.toThrow();
      // State still updates in memory even though persistence failed.
      expect(result.current.history).toHaveLength(1);
    } finally {
      Storage.prototype.setItem = original;
    }
  });

  it('reading does not throw when localStorage.getItem throws', () => {
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = vi.fn(() => {
      throw new DOMException('blocked');
    });

    try {
      expect(() => renderHook(() => useIntentHistory())).not.toThrow();
    } finally {
      Storage.prototype.getItem = original;
    }
  });
});
