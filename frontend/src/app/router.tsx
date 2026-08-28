import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AuthGuard } from "@/features/auth/AuthGuard";
import { AuthPage } from "@/pages/AuthPage";
import { HomePage } from "@/pages/HomePage";
import { ChatPage } from "@/pages/chat/ChatPage";
import { InterviewSetupPage } from "@/pages/interview/InterviewSetupPage";
import { InterviewSessionPage } from "@/pages/interview/InterviewSessionPage";

const InterviewReportsPage = lazy(() => import("@/pages/interview/InterviewReportsPage").then((module) => ({ default: module.InterviewReportsPage })));
const InterviewReportDetailPage = lazy(() => import("@/pages/interview/InterviewReportDetailPage").then((module) => ({ default: module.InterviewReportDetailPage })));
const InterviewSessionReportPage = lazy(() => import("@/pages/interview/InterviewSessionReportPage").then((module) => ({ default: module.InterviewSessionReportPage })));

function LazyReportPage({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="loading-screen"><span className="spinner" />正在加载报告页面…</div>}>{children}</Suspense>;
}

export const appRouter = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/auth", element: <AuthPage /> },
      {
        element: <AuthGuard />,
        children: [
          { path: "/chat", element: <ChatPage /> },
          { path: "/interview", element: <InterviewSetupPage /> },
          { path: "/interview/:sessionId", element: <InterviewSessionPage /> },
          { path: "/interview/reports", element: <LazyReportPage><InterviewReportsPage /></LazyReportPage> },
          { path: "/interview/reports/:reportId", element: <LazyReportPage><InterviewReportDetailPage /></LazyReportPage> },
          { path: "/interview/:sessionId/report", element: <LazyReportPage><InterviewSessionReportPage /></LazyReportPage> },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
