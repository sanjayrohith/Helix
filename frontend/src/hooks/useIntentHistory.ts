import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'helix.intentHistory';
const MAX_ENTRIES = 15;

export interface IntentHistoryEntry {
  intent: string;
  at: string;
  succeeded: boolean;
}

function read(): IntentHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as IntentHistoryEntry[]) : [];
  } catch {
    // A private window or blocked site data must not break the dashboard.
    return [];
  }
}

/** Remembers recent intents so an operator can re-run or tweak one. */
export function useIntentHistory() {
  const [history, setHistory] = useState<IntentHistoryEntry[]>([]);

  useEffect(() => {
    setHistory(read());
  }, []);

  const persist = useCallback((entries: IntentHistoryEntry[]) => {
    setHistory(entries);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
    } catch {
      // Storage being unavailable is not worth surfacing to the operator.
    }
  }, []);

  const record = useCallback(
    (intent: string, succeeded: boolean) => {
      const trimmed = intent.trim();
      if (!trimmed) return;
      const existing = read().filter((entry) => entry.intent !== trimmed);
      persist(
        [{ intent: trimmed, at: new Date().toISOString(), succeeded }, ...existing].slice(
          0,
          MAX_ENTRIES,
        ),
      );
    },
    [persist],
  );

  const clear = useCallback(() => persist([]), [persist]);

  return { history, record, clear };
}
