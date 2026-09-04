import { describe, expect, it } from "vitest";
import { normalizeUser } from "@/services/authService";

describe("normalizeUser", () => {
  it("preserves the UUID returned by FastAPI", () => {
    expect(
      normalizeUser({
        id: "9bc0d992-7a92-44f3-b8fc-3e28e818d5cc",
        username: "candidate",
        email: "candidate@example.test",
      }),
    ).toMatchObject({
      id: "9bc0d992-7a92-44f3-b8fc-3e28e818d5cc",
      username: "candidate",
      mail: "candidate@example.test",
    });
  });

  it("rejects payloads without a username", () => {
    expect(
      normalizeUser({ id: "9bc0d992-7a92-44f3-b8fc-3e28e818d5cc" }),
    ).toBeNull();
  });
});
