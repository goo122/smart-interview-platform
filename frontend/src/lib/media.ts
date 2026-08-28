export type MediaErrorKind =
  | "not_supported"
  | "permission_denied"
  | "not_found"
  | "not_readable"
  | "overconstrained"
  | "unknown";

export type MediaError = {
  kind: MediaErrorKind;
  name?: string;
  message?: string;
};

export const normalizeMediaError = (error: unknown): MediaError => {
  if (error instanceof DOMException) {
    switch (error.name) {
      case "NotAllowedError":
      case "SecurityError":
        return {
          kind: "permission_denied",
          name: error.name,
          message: error.message,
        };
      case "NotFoundError":
        return { kind: "not_found", name: error.name, message: error.message };
      case "NotReadableError":
      case "AbortError":
        return {
          kind: "not_readable",
          name: error.name,
          message: error.message,
        };
      case "OverconstrainedError":
        return {
          kind: "overconstrained",
          name: error.name,
          message: error.message,
        };
      default:
        return { kind: "unknown", name: error.name, message: error.message };
    }
  }
  if (error instanceof Error) {
    return { kind: "unknown", name: error.name, message: error.message };
  }
  return { kind: "unknown" };
};
