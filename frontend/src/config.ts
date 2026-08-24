// Runtime configuration for the HELIX dashboard.
//
// The API and WebSocket endpoints were hard-coded to localhost, which meant
// any deployment other than a developer laptop pointed at the wrong host.
// They now come from Vite environment variables, defaulting to the same
// origin the dashboard is served from so a reverse-proxied deployment works
// with no configuration at all.

const env = import.meta.env as Record<string, string | undefined>;

function resolveApiBase(): string {
  const configured = env.VITE_API_URL?.trim();
  if (configured) return configured.replace(/\/+$/, '');

  if (typeof window !== 'undefined' && window.location.origin) {
    // In dev the API runs on :8000 next to Vite's :5173; in production the
    // dashboard is typically served from the same origin as the API.
    const { protocol, hostname, port } = window.location;
    if (port === '5173') return `${protocol}//${hostname}:8000`;
    return window.location.origin;
  }

  return 'http://localhost:8000';
}

export const API_BASE_URL = resolveApiBase();

export const WS_URL = (() => {
  const configured = env.VITE_WS_URL?.trim();
  if (configured) return configured;
  return `${API_BASE_URL.replace(/^http/, 'ws')}/ws`;
})();

// How often the dashboard re-fetches data if the WebSocket is not connected.
export const POLL_INTERVAL_MS = Number(env.VITE_POLL_INTERVAL_MS ?? 15000);

// Samples kept per slice for the inline sparklines.
export const SPARKLINE_POINTS = 40;
