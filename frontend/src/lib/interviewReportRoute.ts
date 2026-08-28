type ReportLocationState = {
  sessionId?: string;
} | null;

export const getReportSessionIdFromLocation = (location: {
  state: unknown;
  search?: string;
}) => {
  const stateSessionId =
    (location.state as ReportLocationState)?.sessionId?.trim() || "";
  if (stateSessionId) return stateSessionId;

  const fromSearch =
    new URLSearchParams(location.search || "").get("sessionId")?.trim() || "";
  return fromSearch || null;
};

export const buildReportSearch = (sessionId: string | null) =>
  sessionId ? `?sessionId=${encodeURIComponent(sessionId)}` : "";
