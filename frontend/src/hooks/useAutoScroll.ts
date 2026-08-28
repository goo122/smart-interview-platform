import { useEffect, useRef } from "react";

export function useAutoScroll<T>(dependency: T) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      // 适配 Radix UI ScrollArea 的 viewport
      const scrollElement = scrollRef.current.querySelector(
        "[data-radix-scroll-area-viewport]",
      ) as HTMLElement;

      if (scrollElement) {
        scrollElement.scrollTop = scrollElement.scrollHeight;
      } else {
        // 适配普通 div
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
    }
  }, [dependency]);

  return scrollRef;
}
