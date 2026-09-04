import { describe, expect, it } from "vitest";
import { getScopedUserIdentity } from "@/lib/userIdentity";

describe("getScopedUserIdentity", () => {
  it("prefers the backend UUID over the username", () => {
    expect(
      getScopedUserIdentity({
        id: " 9bc0d992-7a92-44f3-b8fc-3e28e818d5cc ",
        username: "candidate",
      }),
    ).toBe("id:9bc0d992-7a92-44f3-b8fc-3e28e818d5cc");
  });

  it("falls back to a normalized username", () => {
    expect(getScopedUserIdentity({ username: " candidate " })).toBe(
      "username:candidate",
    );
  });

  it("returns anonymous when no stable identity exists", () => {
    expect(getScopedUserIdentity({ id: " ", username: " " })).toBe("anonymous");
    expect(getScopedUserIdentity(null)).toBe("anonymous");
  });
});
