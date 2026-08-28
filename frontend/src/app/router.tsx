import { Suspense, lazy, type ReactNode } from "react";
import {
  Navigate,
  createBrowserRouter,
  type RouteObject,
} from "react-router-dom";
import { Loader2 } from "lucide-react";
import AuthGuard from "@/components/auth/AuthGuard";
import AppLayout from "@/layouts/AppLayout";
import { ROUTES } from "@/lib/constants";

const AuthPage = lazy(() => import("@/pages/auth/AuthPage"));
const MarketingHomePage = lazy(
  () => import("@/pages/marketing/MarketingHomePage"),
);
const ChatPage = lazy(() => import("@/pages/chat/ChatPage"));
const InterviewIntroPage = lazy(
  () => import("@/pages/interview/InterviewIntroPage"),
);
const InterviewPage = lazy(() => import("@/pages/interview/InterviewPage"));
const InterviewReportPage = lazy(
  () => import("@/pages/interview/InterviewReportPage"),
);
const InterviewReportDetailPage = lazy(
  () => import("@/pages/interview/InterviewReportDetailPage"),
);

function RouteLoadingScreen() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center bg-white">
      <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
    </div>
  );
}

const withRouteSuspense = (node: ReactNode) => (
  <Suspense fallback={<RouteLoadingScreen />}>{node}</Suspense>
);

export const appRoutes: RouteObject[] = [
  {
    path: ROUTES.home,
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: withRouteSuspense(<MarketingHomePage />),
      },
      {
        path: ROUTES.auth,
        element: withRouteSuspense(<AuthPage />),
      },
      {
        element: <AuthGuard />,
        children: [
          {
            path: ROUTES.interviewIntro,
            element: withRouteSuspense(<InterviewIntroPage />),
          },
          {
            path: ROUTES.interviewRoom,
            element: withRouteSuspense(<InterviewPage />),
          },
          {
            path: `${ROUTES.interviewRoom}/:sessionId`,
            element: withRouteSuspense(<InterviewPage />),
          },
          {
            path: ROUTES.interviewReport,
            element: withRouteSuspense(<InterviewReportPage />),
          },
          {
            path: ROUTES.interviewReportDetail,
            element: withRouteSuspense(<InterviewReportDetailPage />),
          },
          {
            path: `${ROUTES.chat}/:sessionId?`,
            element: withRouteSuspense(<ChatPage />),
          },
          {
            path: ROUTES.questionBank,
            element: <Navigate to={ROUTES.chat} replace />,
          },
          {
            path: ROUTES.questionBankManage,
            element: <Navigate to={ROUTES.chat} replace />,
          },
        ],
      },
    ],
  },
];

export const appRouter = createBrowserRouter(appRoutes);
