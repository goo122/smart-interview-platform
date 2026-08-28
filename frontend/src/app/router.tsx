import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AuthGuard } from "@/features/auth/AuthGuard";
import { AuthPage } from "@/pages/AuthPage";
import { HomePage } from "@/pages/HomePage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { ChatPage } from "@/pages/chat/ChatPage";

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
          { path: "/interview", element: <PlaceholderPage title="模拟面试" description="面试房间将在下一阶段接入。" /> },
          { path: "/interview/reports", element: <PlaceholderPage title="面试报告" description="报告页面将在下一阶段接入。" /> },
        ],
      },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
