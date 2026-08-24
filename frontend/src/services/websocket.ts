// WebSocket client for real-time slice, telemetry and SLA updates.

import { WS_URL } from '../config';
import type { WebSocketEvent, WebSocketMessage } from '../types/slice';

type MessageHandler = (message: WebSocketMessage) => void;
export type ConnectionState = 'connecting' | 'open' | 'closed' | 'failed';
type StateHandler = (state: ConnectionState) => void;

const MAX_RECONNECT_DELAY_MS = 30_000;
const HEARTBEAT_INTERVAL_MS = 25_000;

class WebSocketService {
  private socket: WebSocket | null = null;
  private handlers = new Map<WebSocketEvent | 'all', Set<MessageHandler>>();
  private stateHandlers = new Set<StateHandler>();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 8;
  private baseDelay = 1000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionallyClosed = false;
  private state: ConnectionState = 'closed';

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN || this.state === 'connecting') return;

    this.intentionallyClosed = false;
    this.setState('connecting');

    try {
      this.socket = new WebSocket(WS_URL);
    } catch (error) {
      console.error('[WebSocket] Could not open a connection:', error);
      this.scheduleReconnect();
      return;
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setState('open');
      this.startHeartbeat();
    };

    this.socket.onmessage = (event) => {
      // The server answers heartbeats with a bare "pong", which is not JSON.
      if (event.data === 'pong') return;
      try {
        this.notify(JSON.parse(event.data) as WebSocketMessage);
      } catch (error) {
        console.error('[WebSocket] Could not parse message:', error);
      }
    };

    this.socket.onclose = () => {
      this.stopHeartbeat();
      this.socket = null;
      if (this.intentionallyClosed) {
        this.setState('closed');
        return;
      }
      this.scheduleReconnect();
    };

    this.socket.onerror = () => {
      // onclose always follows, so reconnection is handled there.
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.warn('[WebSocket] Giving up after %d attempts', this.reconnectAttempts);
      this.setState('failed');
      return;
    }

    this.reconnectAttempts += 1;
    // Exponential backoff with jitter, so a restarted backend is not hit by
    // every open dashboard at the same instant.
    const backoff = Math.min(
      this.baseDelay * 2 ** (this.reconnectAttempts - 1),
      MAX_RECONNECT_DELAY_MS,
    );
    const delay = backoff * (0.75 + Math.random() * 0.5);
    this.setState('connecting');

    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => this.sendPing(), HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.socket?.close();
    this.socket = null;
    this.setState('closed');
  }

  /** Reset the backoff and try again, for a user-initiated retry. */
  retry(): void {
    this.reconnectAttempts = 0;
    this.connect();
  }

  subscribe(event: WebSocketEvent | 'all', handler: MessageHandler): () => void {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event)!.add(handler);
    return () => {
      this.handlers.get(event)?.delete(handler);
    };
  }

  onStateChange(handler: StateHandler): () => void {
    this.stateHandlers.add(handler);
    handler(this.state);
    return () => {
      this.stateHandlers.delete(handler);
    };
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  private setState(state: ConnectionState): void {
    if (this.state === state) return;
    this.state = state;
    this.stateHandlers.forEach((handler) => handler(state));
  }

  private notify(message: WebSocketMessage): void {
    this.handlers.get(message.event)?.forEach((handler) => handler(message));
    this.handlers.get('all')?.forEach((handler) => handler(message));
  }

  sendPing(): void {
    if (this.socket?.readyState === WebSocket.OPEN) this.socket.send('ping');
  }
}

export const websocketService = new WebSocketService();
