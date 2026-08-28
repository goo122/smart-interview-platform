import { useState, type SetStateAction } from "react";

const INTERVIEW_SESSION_STORAGE_KEY = "interview.activeSessionId";

type InterviewStorageUser = {
  id?: number | null;
  username?: string | null;
} | null;

const getInterviewStorageIdentity = (user: InterviewStorageUser) => {
  if (!user) return null;
  if (typeof user.id === "number" && Number.isFinite(user.id) && user.id > 0) {
    return `id:${user.id}`;
  }
  const username = user.username?.trim();
  if (username) {
    return `username:${username}`;
  }
  return null;
};

const getInterviewSessionStorageKey = (identity: string) =>
  `${INTERVIEW_SESSION_STORAGE_KEY}.${identity}`;

const readStoredSessionId = (sessionStorageKey: string | null) => {
  if (!sessionStorageKey) return null;
  const scopedSessionId = window.sessionStorage.getItem(sessionStorageKey);
  return scopedSessionId;
};

export function useInterviewSessionStorage(user: InterviewStorageUser) {
  const storageIdentity = getInterviewStorageIdentity(user);
  const sessionStorageKey = storageIdentity
    ? getInterviewSessionStorageKey(storageIdentity)
    : null;

  const [, forceRender] = useState(0);
  const interviewerSessionId = readStoredSessionId(sessionStorageKey);

  const setInterviewerSessionId = (
    nextValue: SetStateAction<string | null>,
  ) => {
    const previous = readStoredSessionId(sessionStorageKey);
    const resolvedValue =
      typeof nextValue === "function"
        ? (nextValue as (prevState: string | null) => string | null)(previous)
        : nextValue;

    if (sessionStorageKey) {
      if (resolvedValue) {
        window.sessionStorage.setItem(sessionStorageKey, resolvedValue);
      } else {
        window.sessionStorage.removeItem(sessionStorageKey);
      }
    }
    window.sessionStorage.removeItem(INTERVIEW_SESSION_STORAGE_KEY);
    forceRender((value) => value + 1);
  };

  const clearStoredSession = () => {
    if (sessionStorageKey) {
      window.sessionStorage.removeItem(sessionStorageKey);
    }
    window.sessionStorage.removeItem(INTERVIEW_SESSION_STORAGE_KEY);
    forceRender((value) => value + 1);
  };

  return {
    interviewerSessionId,
    setInterviewerSessionId,
    clearStoredSession,
  };
}
