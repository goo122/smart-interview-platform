import { getAuthToken } from "@/lib/authToken";
import {
  resolveApiBaseUrl,
  resolveRuntimeWsBaseUrl,
  resolveWsBaseUrl,
} from "@/config/env";
import {
  resolveAudioTranscriptionEvent,
  type AudioToTextIncomingMessage,
} from "@/lib/audioTranscription";

export class AudioToTextWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private pendingBinaryQueue: Array<ArrayBuffer | Blob> = [];
  private readonly maxPendingBinaryChunks = 24;
  private hasOpened = false;
  private lastMessageTimestamp = 0;
  private lastMessageKey: string | null = null;
  private lastMessageRevision = 0;
  private gracefulCloseRequested = false;
  private serverClosed = false;
  private errorReported = false;
  private stopWaiter: {
    promise: Promise<void>;
    resolve: () => void;
    timer: ReturnType<typeof setTimeout>;
  } | null = null;

  public onTranscription?: (text: string) => void;
  public onFinal?: (text: string) => void;
  public onError?: (error: string) => void;
  public onConnected?: () => void;
  public onDisconnected?: () => void;

  constructor(userId: string) {
    this.url = this.buildWebSocketUrl(userId);
  }

  private resolveConfiguredWebSocketBaseUrl() {
    return resolveWsBaseUrl(import.meta.env.VITE_WS_BASE_URL);
  }

  private buildWebSocketUrl(userId: string) {
    const wsBase = this.resolveWebSocketBaseUrl();
    const apiBase = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL);
    const path = `${apiBase}/xunzhi/v1/xunfei/audio-to-text/${encodeURIComponent(userId)}`;
    const token = getAuthToken();

    if (!token) {
      return `${wsBase}${path}`;
    }

    const query = new URLSearchParams();
    query.set("token", token);
    return `${wsBase}${path}?${query.toString()}`;
  }

  private resolveWebSocketBaseUrl() {
    const configuredWsBase = this.resolveConfiguredWebSocketBaseUrl();
    return resolveRuntimeWsBaseUrl(window.location, configuredWsBase);
  }

  connect() {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.CONNECTING ||
        this.ws.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    this.ws = new WebSocket(this.url);
    this.resetMessageCursor();
    this.gracefulCloseRequested = false;
    this.serverClosed = false;
    this.errorReported = false;

    this.ws.onopen = () => {
      console.log("WebSocket Connected");
      this.hasOpened = true;
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AudioToTextIncomingMessage;
        this.handleMessage(data);
      } catch (error) {
        console.error("Failed to parse WS message", error);
      }
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket Error", error);
      this.reportError("WebSocket connection error");
    };

    this.ws.onclose = (event) => {
      console.warn("WebSocket Disconnected", {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });
      this.stopPing();
      if (!this.hasOpened && event.code !== 1000) {
        const details = [event.code ? `code=${event.code}` : null, event.reason]
          .filter(Boolean)
          .join(", ");
        this.reportError(
          details
            ? `WebSocket closed before ready: ${details}`
            : "WebSocket closed before ready",
        );
      }
      if (
        this.hasOpened &&
        !this.gracefulCloseRequested &&
        !this.serverClosed &&
        event.code !== 1000
      ) {
        this.reportError("语音转写连接已断开，请重新开始录音。");
      }
      this.resolveStopWaiter();
      this.onDisconnected?.();
      this.ws = null;
      this.hasOpened = false;
    };
  }

  private handleMessage(data: AudioToTextIncomingMessage) {
    const event = resolveAudioTranscriptionEvent(data);
    if (!this.shouldApplyEvent(data, event)) {
      return;
    }

    switch (event.kind) {
      case "reset":
        this.onTranscription?.("");
        break;
      case "replace":
        this.onTranscription?.(event.text);
        break;
      case "archive":
        this.onFinal?.(event.text);
        break;
      case "connected":
        this.onConnected?.();
        this.flushPendingBinaryQueue();
        break;
      case "control":
      case "heartbeat":
        break;
      case "error":
        this.reportError(event.message);
        break;
      case "closed":
        this.serverClosed = true;
        this.resolveStopWaiter();
        break;
      case "unknown":
        console.warn("Unknown message type:", event.type);
        break;
    }
  }

  private startPing() {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      this.sendCommand("ping");
    }, 15000);
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  sendCommand(
    type: "ping" | "start_transcription" | "stop_transcription" | "get_status",
    payload?: Record<string, unknown>,
  ) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...payload }));
    }
  }

  async stopTranscription(timeoutMs = 3000) {
    if (!this.ws) {
      return;
    }

    this.gracefulCloseRequested = true;
    if (this.ws.readyState !== WebSocket.OPEN) {
      this.resolveStopWaiter();
      return;
    }

    if (this.stopWaiter) {
      await this.stopWaiter.promise;
      return;
    }

    let resolveWaiter: () => void = () => undefined;
    const promise = new Promise<void>((resolve) => {
      resolveWaiter = resolve;
    });
    const timer = setTimeout(resolveWaiter, timeoutMs);
    this.stopWaiter = { promise, resolve: resolveWaiter, timer };
    this.sendCommand("stop_transcription");
    await promise;
  }

  sendAudio(data: Blob | ArrayBuffer) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    } else if (this.ws?.readyState === WebSocket.CONNECTING) {
      if (this.pendingBinaryQueue.length >= this.maxPendingBinaryChunks) {
        this.pendingBinaryQueue.shift();
      }
      this.pendingBinaryQueue.push(data);
    } else {
      console.warn("Cannot send audio: WebSocket is not open");
    }
  }

  disconnect() {
    this.gracefulCloseRequested = true;
    this.stopPing();
    this.pendingBinaryQueue = [];
    this.resetMessageCursor();
    this.resolveStopWaiter();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private flushPendingBinaryQueue() {
    if (
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN ||
      this.pendingBinaryQueue.length === 0
    ) {
      return;
    }
    this.pendingBinaryQueue.forEach((chunk) => {
      this.ws?.send(chunk);
    });
    this.pendingBinaryQueue = [];
  }

  private resetMessageCursor() {
    this.lastMessageTimestamp = 0;
    this.lastMessageKey = null;
    this.lastMessageRevision = 0;
  }

  private reportError(message: string) {
    if (this.errorReported) {
      return;
    }
    this.errorReported = true;
    this.onError?.(message);
  }

  private resolveStopWaiter() {
    if (!this.stopWaiter) {
      return;
    }
    const waiter = this.stopWaiter;
    this.stopWaiter = null;
    clearTimeout(waiter.timer);
    waiter.resolve();
  }

  private shouldApplyEvent(
    message: AudioToTextIncomingMessage,
    event: ReturnType<typeof resolveAudioTranscriptionEvent>,
  ) {
    const text =
      "text" in event
        ? event.text
        : "message" in event
          ? event.message
          : "";
    const nextKey = `${event.kind}:${message.type ?? ""}:${text}`;
    const nextTimestamp =
      typeof message.timestamp === "number" ? message.timestamp : null;
    const nextRevision =
      typeof message.revision === "number" ? message.revision : null;

    if (nextRevision !== null) {
      if (nextRevision < this.lastMessageRevision) {
        return false;
      }
      if (
        nextRevision === this.lastMessageRevision &&
        nextKey === this.lastMessageKey
      ) {
        return false;
      }
      this.lastMessageRevision = nextRevision;
    }

    if (nextTimestamp !== null) {
      if (nextTimestamp < this.lastMessageTimestamp) {
        return false;
      }
      if (
        nextTimestamp === this.lastMessageTimestamp &&
        nextKey === this.lastMessageKey
      ) {
        return false;
      }
      this.lastMessageTimestamp = nextTimestamp;
      this.lastMessageKey = nextKey;
      return true;
    }

    if (nextKey === this.lastMessageKey) {
      return false;
    }
    this.lastMessageKey = nextKey;
    return true;
  }
}
