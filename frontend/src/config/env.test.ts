import { describe, expect, it } from "vitest";
import {
  resolveApiBaseUrl,
  resolveAppEnv,
  resolveRuntimeWsBaseUrl,
  resolveWsBaseUrl,
} from "@/config/env";

describe("env utilities", () => {
  it("resolveApiBaseUrl should use default and trim trailing slash", () => {
    expect(resolveApiBaseUrl(undefined)).toBe("/api");
    expect(resolveApiBaseUrl("/api/")).toBe("/api");
  });

  it("resolveAppEnv should fallback to defaults", () => {
    const env = resolveAppEnv({});
    expect(env.apiBaseUrl).toBe("/api");
    expect(env.apiTarget).toBe("http://localhost:8000");
    expect(env.wsBaseUrl).toBeNull();
  });

  it("resolveWsBaseUrl should normalize configured value", () => {
    expect(resolveWsBaseUrl(" ws://localhost:9000/ ")).toBe(
      "ws://localhost:9000",
    );
    expect(resolveWsBaseUrl("")).toBeNull();
  });

  it("resolveRuntimeWsBaseUrl should infer protocol from location", () => {
    expect(
      resolveRuntimeWsBaseUrl(
        { protocol: "https:", host: "example.com" } as Location,
        null,
      ),
    ).toBe("wss://example.com");
    expect(
      resolveRuntimeWsBaseUrl(
        { protocol: "http:", host: "example.com:5173" } as Location,
        null,
      ),
    ).toBe("ws://example.com:5173");
  });

  it("resolveRuntimeWsBaseUrl should prefer configured value", () => {
    expect(
      resolveRuntimeWsBaseUrl(
        { protocol: "https:", host: "example.com" } as Location,
        "wss://custom.example.com",
      ),
    ).toBe("wss://custom.example.com");
  });
});
