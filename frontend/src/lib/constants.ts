export const ROUTES = {
  home: "/",
  interviewIntro: "/interview",
  interviewRoom: "/interview/room",
  interviewReport: "/interview/report",
  interviewReportDetail: "/interview/report/detail",
  chat: "/chat",
  questionBank: "/question-bank",
  questionBankManage: "/question-bank/manage",
  auth: "/auth",
} as const;

export const CHAT_ROLES = {
  user: "user",
  assistant: "assistant",
} as const;

export type ChatRole = (typeof CHAT_ROLES)[keyof typeof CHAT_ROLES];

export const INTERVIEW_DEFAULTS = {
  initialMessageId: "1",
  assistantWelcomeMessage:
    "你好！我是你的 AI 面试官。请先上传你的简历，我们开始今天的模拟面试。",
  assistantFollowupMessage:
    "收到你的回答。这是一个很好的切入点，但你能更详细地解释一下具体实现细节吗？",
  aiReplyDelayMs: 1500,
  resumeAccept: ".pdf",
} as const;

export const MEDIA_TARGETS = {
  camera: "camera",
  microphone: "microphone",
} as const;

export type MediaTarget = (typeof MEDIA_TARGETS)[keyof typeof MEDIA_TARGETS];
