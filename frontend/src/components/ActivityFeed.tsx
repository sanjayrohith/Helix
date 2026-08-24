import { useEffect, useState } from 'react';
import { getEvents } from '../services/api';
import type { AuditEvent } from '../types/telemetry';

const SEVERITY_DOT: Record<string, string> = {
  info: 'bg-cyan',
  warning: 'bg-amber-400',
  error: 'bg-rose-400',
};

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function ActivityFeed({ refreshKey }: { refreshKey: number }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [severity, setSeverity] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getEvents({ limit: 40, severity: severity ?? undefined })
      .then((result) => {
        if (!cancelled) setEvents(result);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey, severity]);

  return (
    <section className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03]">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-3">
          <h2 className="font-syne text-sm text-slate-100">Activity</h2>
          <span className="font-mono text-[11px] text-slate-400">{events.length} events</span>
        </div>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? '' : 'rotate-180'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {!collapsed && (
        <div className="border-t border-white/10">
          <div className="flex gap-1.5 px-4 py-2">
            {[null, 'info', 'warning', 'error'].map((level) => (
              <button
                key={level ?? 'all'}
                onClick={() => setSeverity(level)}
                className={`rounded px-2 py-0.5 font-syne text-[11px] transition-colors ${
                  severity === level
                    ? 'border border-cyan/35 bg-cyan/20 text-cyan-100'
                    : 'border border-white/10 text-slate-400 hover:text-white'
                }`}
              >
                {level ?? 'all'}
              </button>
            ))}
          </div>

          {events.length === 0 ? (
            <p className="px-4 pb-3 text-xs text-slate-400">No events recorded yet.</p>
          ) : (
            <ul className="max-h-72 divide-y divide-white/5 overflow-y-auto">
              {events.map((event) => (
                <li key={event.event_id} className="flex items-start gap-2.5 px-4 py-2">
                  <span
                    className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                      SEVERITY_DOT[event.severity] ?? 'bg-slate-500'
                    }`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-slate-200">{event.summary}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-slate-500">
                      {event.event_type} · {event.actor}
                    </p>
                  </div>
                  <span className="shrink-0 font-mono text-[10px] text-slate-500">
                    {relativeTime(event.timestamp)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
