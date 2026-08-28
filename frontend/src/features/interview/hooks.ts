import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { interviewApi } from "@/features/interview/api";
import { interviewPollInterval } from "@/features/interview/state";

export const interviewKeys = {
  all: ["interview"] as const,
  sessions: (current = 1, size = 20) => [...interviewKeys.all, "sessions", current, size] as const,
  session: (sessionId: string) => [...interviewKeys.all, "session", sessionId] as const,
  questions: (sessionId: string) => [...interviewKeys.all, "questions", sessionId] as const,
  currentTurn: (sessionId: string) => [...interviewKeys.all, "current-turn", sessionId] as const,
  turns: (sessionId: string) => [...interviewKeys.all, "turns", sessionId] as const,
  turn: (sessionId: string, turnId: string) => [...interviewKeys.all, "turn", sessionId, turnId] as const,
};

export function useInterviewSessions() {
  return useQuery({ queryKey: interviewKeys.sessions(), queryFn: () => interviewApi.listSessions(), staleTime: 10_000 });
}

export function useInterviewSession(sessionId: string) {
  return useQuery({
    queryKey: interviewKeys.session(sessionId),
    queryFn: () => interviewApi.getSession(sessionId),
    enabled: Boolean(sessionId),
    staleTime: 500,
    refetchInterval: (query) => interviewPollInterval(query.state.data?.status),
    refetchIntervalInBackground: false,
  });
}

export function useInterviewQuestions(sessionId: string, enabled: boolean) {
  return useQuery({ queryKey: interviewKeys.questions(sessionId), queryFn: () => interviewApi.getQuestions(sessionId), enabled, staleTime: Infinity });
}

export function useCurrentTurn(sessionId: string, enabled: boolean) {
  return useQuery({
    queryKey: interviewKeys.currentTurn(sessionId),
    queryFn: () => interviewApi.getCurrentTurn(sessionId),
    enabled,
    staleTime: 500,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (!query.state.data && query.state.fetchFailureCount >= 2) return false;
      return status === "EVALUATING" || !query.state.data ? 1_500 : false;
    },
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useInterviewTurns(sessionId: string, enabled = true) {
  return useQuery({ queryKey: interviewKeys.turns(sessionId), queryFn: () => interviewApi.listTurns(sessionId), enabled, staleTime: 1_000 });
}

export function useInterviewMutations(sessionId?: string) {
  const queryClient = useQueryClient();
  const createInFlight = useRef<ReturnType<typeof interviewApi.createSession> | null>(null);
  const startInFlight = useRef<ReturnType<typeof interviewApi.startSession> | null>(null);
  const submitInFlight = useRef(new Map<string, ReturnType<typeof interviewApi.submitAnswer>>());
  const invalidateSession = async (id: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: interviewKeys.session(id) }),
      queryClient.invalidateQueries({ queryKey: interviewKeys.currentTurn(id) }),
      queryClient.invalidateQueries({ queryKey: interviewKeys.turns(id) }),
      queryClient.invalidateQueries({ queryKey: interviewKeys.sessions() }),
    ]);
  };
  const create = useMutation({
    mutationFn: async (payload: Parameters<typeof interviewApi.createSession>[0]) => {
      if (createInFlight.current) return createInFlight.current;
      const request = interviewApi.createSession(payload);
      createInFlight.current = request;
      try {
        return await request;
      } finally {
        createInFlight.current = null;
      }
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: interviewKeys.sessions() }),
  });
  const start = useMutation({
    mutationFn: async (id: string) => {
      if (startInFlight.current) return startInFlight.current;
      const request = interviewApi.startSession(id);
      startInFlight.current = request;
      try {
        return await request;
      } finally {
        startInFlight.current = null;
      }
    },
    onSuccess: (session) => invalidateSession(session.sessionId),
  });
  const cancel = useMutation({ mutationFn: interviewApi.cancelSession, onSuccess: (session) => invalidateSession(session.sessionId) });
  const submit = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Parameters<typeof interviewApi.submitAnswer>[1] }) => {
      const key = `${id}:${payload.turnId}:${payload.requestId}`;
      const existing = submitInFlight.current.get(key);
      if (existing) return existing;
      const request = interviewApi.submitAnswer(id, payload);
      submitInFlight.current.set(key, request);
      try {
        return await request;
      } finally {
        submitInFlight.current.delete(key);
      }
    },
    onSuccess: (_, variables) => invalidateSession(variables.id),
  });
  return { create, start, cancel, submit, sessionId };
}
