import { describe, expect, it } from "vitest";
import {
  isAbortError,
  normalizeBase64Audio,
} from "@/hooks/audio/chatTtsPlayback.shared";

describe("chatTtsPlayback.shared", () => {
  it("normalizes base64 audio payloads", () => {
    expect(
      normalizeBase64Audio(" data:audio/mpeg;base64,QUJDRA==\n "),
    ).toBe("QUJDRA==");

    expect(normalizeBase64Audio("QUJD-RA__")).toBe("QUJD+RA//");
  });

  it("detects abort-style errors", () => {
    expect(isAbortError(new DOMException("aborted", "AbortError"))).toBe(true);
    expect(isAbortError(new Error("other"))).toBe(false);
  });
});
