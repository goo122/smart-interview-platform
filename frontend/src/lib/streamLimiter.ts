export interface TextStreamLimiterOptions {
  onUpdate: (value: string) => void;
  intervalMs?: number;
  charsPerTick?: number;
  initialValue?: string;
}

export interface TextStreamLimiter {
  push: (chunk: string) => void;
  flush: () => void;
  stop: () => void;
  getValue: () => string;
}

const DEFAULT_INTERVAL_MS = 40;
const DEFAULT_CHARS_PER_TICK = 12;

export function createTextStreamLimiter(
  options: TextStreamLimiterOptions,
): TextStreamLimiter {
  const intervalMs =
    options.intervalMs && options.intervalMs > 0
      ? options.intervalMs
      : DEFAULT_INTERVAL_MS;
  const charsPerTick =
    options.charsPerTick && options.charsPerTick > 0
      ? options.charsPerTick
      : DEFAULT_CHARS_PER_TICK;

  let value = options.initialValue ?? "";
  let pending = "";
  let timer: ReturnType<typeof setInterval> | null = null;

  const stopTimer = () => {
    if (!timer) return;
    clearInterval(timer);
    timer = null;
  };

  const tick = () => {
    if (!pending) {
      stopTimer();
      return;
    }

    const nextChunk = pending.slice(0, charsPerTick);
    pending = pending.slice(nextChunk.length);
    value += nextChunk;
    options.onUpdate(value);

    if (!pending) {
      stopTimer();
    }
  };

  const ensureTimer = () => {
    if (timer) return;
    timer = setInterval(tick, intervalMs);
  };

  return {
    push(chunk: string) {
      if (!chunk) return;
      pending += chunk;

      if (!timer) {
        tick();
        ensureTimer();
      }
    },
    flush() {
      if (!pending) return;
      value += pending;
      pending = "";
      options.onUpdate(value);
      stopTimer();
    },
    stop() {
      pending = "";
      stopTimer();
    },
    getValue() {
      return value;
    },
  };
}
