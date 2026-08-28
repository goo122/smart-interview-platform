export const createRequestId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `interview-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

export const interviewPollInterval = (status: string | undefined) => {
  if (status === "CREATED") return 1_500;
  if (status === "PREPARING") return 2_500;
  if (status === "IN_PROGRESS") return 1_500;
  return false;
};

export const isCurrentTurn = (sessionId: string, turnId: string | undefined, value: { sessionId?: string; turnId?: string } | undefined) =>
  Boolean(value && value.sessionId === sessionId && value.turnId === turnId);
