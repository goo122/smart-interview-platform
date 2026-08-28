import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { ChatMessage } from "@/lib/chat";
import { checkAuthStatus, logoutUser } from "@/store/slices/userSlice";

export interface PendingOutbound {
  requestId: string;
  sessionId: string;
  assistantMessageId: string;
  content: string;
  aiId?: number;
}

export interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  currentSessionId: string | null;
  currentSessionTitle: string | null;
  pendingOutbound: PendingOutbound | null;
  activeStreamRequestId: string | null;
  activeStreamSessionId: string | null;
  activeStreamMessageId: string | null;
}

export const initialState: ChatState = {
  messages: [],
  isStreaming: false,
  error: null,
  currentSessionId: null,
  currentSessionTitle: null,
  pendingOutbound: null,
  activeStreamRequestId: null,
  activeStreamSessionId: null,
  activeStreamMessageId: null,
};

const resetRuntimeState = (state: ChatState) => {
  state.messages = [];
  state.isStreaming = false;
  state.error = null;
  state.currentSessionId = null;
  state.currentSessionTitle = null;
  state.pendingOutbound = null;
  state.activeStreamRequestId = null;
  state.activeStreamSessionId = null;
  state.activeStreamMessageId = null;
};

export const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    resetChatRuntime: (state) => {
      resetRuntimeState(state);
    },
    setChatRuntimeSession: (
      state,
      action: PayloadAction<{ sessionId: string; title: string }>,
    ) => {
      state.currentSessionId = action.payload.sessionId;
      state.currentSessionTitle = action.payload.title;
      state.error = null;
    },
    hydrateChatSession: (
      state,
      action: PayloadAction<{
        sessionId: string;
        title: string;
        messages: ChatMessage[];
      }>,
    ) => {
      state.currentSessionId = action.payload.sessionId;
      state.currentSessionTitle = action.payload.title;
      state.messages = action.payload.messages;
      state.error = null;
      state.isStreaming = false;
      state.pendingOutbound = null;
      state.activeStreamRequestId = null;
      state.activeStreamSessionId = null;
      state.activeStreamMessageId = null;
    },
    setPendingOutbound: (
      state,
      action: PayloadAction<PendingOutbound | null>,
    ) => {
      state.pendingOutbound = action.payload;
    },
    appendUserMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
      state.error = null;
    },
    appendAssistantPlaceholder: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
      state.error = null;
    },
    appendAssistantChunk: (
      state,
      action: PayloadAction<{ id: string; content: string }>,
    ) => {
      const message = state.messages.find(
        (item) => item.id === action.payload.id,
      );
      if (!message) {
        return;
      }
      message.content = action.payload.content;
      message.status = "streaming";
    },
    appendAssistantReasoningChunk: (
      state,
      action: PayloadAction<{ id: string; reasoning: string }>,
    ) => {
      const message = state.messages.find(
        (item) => item.id === action.payload.id,
      );
      if (!message) {
        return;
      }
      message.reasoning = action.payload.reasoning;
      message.status = "streaming";
    },
    finishAssistantMessage: (state, action: PayloadAction<{ id: string }>) => {
      const message = state.messages.find(
        (item) => item.id === action.payload.id,
      );
      if (!message) {
        return;
      }
      message.status = "done";
    },
    failAssistantMessage: (
      state,
      action: PayloadAction<{ id: string; errorMessage: string }>,
    ) => {
      const message = state.messages.find(
        (item) => item.id === action.payload.id,
      );
      if (!message) {
        return;
      }
      if (!message.content.trim()) {
        message.content = action.payload.errorMessage;
      }
      message.status = "error";
      state.error = action.payload.errorMessage;
    },
    setActiveStream: (
      state,
      action: PayloadAction<{
        requestId: string;
        sessionId: string;
        messageId: string;
      } | null>,
    ) => {
      state.isStreaming = Boolean(action.payload);
      state.activeStreamRequestId = action.payload?.requestId ?? null;
      state.activeStreamSessionId = action.payload?.sessionId ?? null;
      state.activeStreamMessageId = action.payload?.messageId ?? null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(checkAuthStatus.rejected, (state, action) => {
        if (!action.payload?.shouldClearAuth) {
          return;
        }
        resetRuntimeState(state);
      })
      .addCase(logoutUser.fulfilled, (state) => {
        resetRuntimeState(state);
      });
  },
});

export const {
  resetChatRuntime,
  setChatRuntimeSession,
  hydrateChatSession,
  setPendingOutbound,
  appendUserMessage,
  appendAssistantPlaceholder,
  appendAssistantChunk,
  appendAssistantReasoningChunk,
  finishAssistantMessage,
  failAssistantMessage,
  setActiveStream,
} = chatSlice.actions;

export default chatSlice.reducer;
