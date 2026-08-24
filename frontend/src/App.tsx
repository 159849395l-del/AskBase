/** 应用根组件 — 路由配置 */

import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider, App as AntApp, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { useAuthStore } from "./store/authStore";

// 页面
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ChatPage from "./pages/ChatPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import AgentListPage from "./pages/AgentListPage";
import AgentEditPage from "./pages/AgentEditPage";
import ProfilePage from "./pages/ProfilePage";
import NotFoundPage from "./pages/NotFoundPage";

// 爬虫管理页面
import CrawlerTaskListPage from "./pages/CrawlerTaskListPage";
import CrawlerTaskCreatePage from "./pages/CrawlerTaskCreatePage";
import CrawlerTaskDetailPage from "./pages/CrawlerTaskDetailPage";
import CrawlerResultPage from "./pages/CrawlerResultPage";

// 组件
import ProtectedRoute from "./components/common/ProtectedRoute";
import AppLayout from "./components/layout/AppLayout";

const App: React.FC = () => {
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: "#1677ff",
          borderRadius: 6,
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Routes>
            {/* 公开路由 */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* 受保护路由 — AppLayout */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/chat/:convId" element={<ChatPage />} />
              <Route
                path="/admin/kb"
                element={
                  <ProtectedRoute requireAdmin>
                    <KnowledgeBasePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/agents"
                element={
                  <ProtectedRoute requireAdmin>
                    <AgentListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/agents/new"
                element={
                  <ProtectedRoute requireAdmin>
                    <AgentEditPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/agents/:id/edit"
                element={
                  <ProtectedRoute requireAdmin>
                    <AgentEditPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/crawler/tasks"
                element={
                  <ProtectedRoute requireAdmin>
                    <CrawlerTaskListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/crawler/tasks/new"
                element={
                  <ProtectedRoute requireAdmin>
                    <CrawlerTaskCreatePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/crawler/tasks/:taskId"
                element={
                  <ProtectedRoute requireAdmin>
                    <CrawlerTaskDetailPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/crawler/tasks/:taskId/results/:resultId"
                element={
                  <ProtectedRoute requireAdmin>
                    <CrawlerResultPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/profile" element={<ProfilePage />} />
            </Route>

            {/* 根路径重定向 */}
            <Route path="/" element={<Navigate to="/chat" replace />} />

            {/* 404 */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
};

export default App;
