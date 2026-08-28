import { useCallback, useRef, useState } from "react";

type StreamHandlers = {
  onOpen?: () => void;
  onToken?: (token: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
};

const parseToken = (data: string) => {
  if (data === "[DONE]") {
    return { done: true, token: "" };
  }
  try {
    const parsed = JSON.parse(data) as { token?: string; done?: boolean };
    return { done: Boolean(parsed.done), token: parsed.token ?? data };
  } catch {
    return { done: false, token: data };
  }
};

export default function useSSEStream() {
  const sourceRef = useRef<EventSource | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const stop = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setIsStreaming(false);
  }, []);

  const start = useCallback(
    (url: string, handlers?: StreamHandlers) => {
      stop();
      const source = new EventSource(url);
      sourceRef.current = source;
      setIsStreaming(true);

      source.onopen = () => {
        handlers?.onOpen?.();
      };

      source.onmessage = (event) => {
        const { done, token } = parseToken(event.data);
        if (done) {
          handlers?.onDone?.();
          stop();
          return;
        }
        if (token) {
          handlers?.onToken?.(token);
        }
      };

      source.onerror = () => {
        handlers?.onError?.(new Error("SSE 连接失败"));
        stop();
      };
    },
    [stop],
  );

  return { start, stop, isStreaming };
}
