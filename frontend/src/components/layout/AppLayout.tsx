/** 应用主布局 — 侧边栏 + 内容区 */

import React, { useState, useEffect } from "react";
import { Layout, Menu, Button, theme } from "antd";
import {
  MessageOutlined,
  DatabaseOutlined,
  RobotOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BugOutlined,
  ApiOutlined,
  TeamOutlined,
  BulbOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";
import { useChatStore } from "../../store/chatStore";

const { Header, Sider, Content } = Layout;

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((s) => s.logout);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const user = useAuthStore((s) => s.user);
  const resetChat = useChatStore((s) => s.reset);

  const { token: themeToken } = theme.useToken();

  useEffect(() => {
    // Reset chat store when user changes (different user logged in)
    resetChat();
  }, [user?.id]);

  const menuItems = [
    {
      key: "/chat",
      icon: <MessageOutlined />,
      label: "我的会话",
    },
    ...(isAdmin
      ? [
          {
            key: "/admin/agents",
            icon: <RobotOutlined />,
            label: "智能体管理",
          },
          {
            key: "/admin/kb",
            icon: <DatabaseOutlined />,
            label: "知识库管理",
          },
          {
            key: "/admin/datasources",
            icon: <ApiOutlined />,
            label: "数据源管理",
          },
          {
            key: "/admin/models",
            icon: <BulbOutlined />,
            label: "大模型库",
          },
          {
            key: "/admin/tools",
            icon: <ToolOutlined />,
            label: "AI 智能工具",
          },
          {
            key: "/admin/crawler/tasks",
            icon: <BugOutlined />,
            label: "爬虫管理",
          },
          {
            key: "/admin/users",
            icon: <TeamOutlined />,
            label: "用户管理",
          },
        ]
      : []),
    {
      key: "/profile",
      icon: <UserOutlined />,
      label: "个人中心",
    },
  ];

  const selectedKey = menuItems
    .map((item) => item.key)
    .find((key) => location.pathname.startsWith(key)) || "/chat";

  return (
    <Layout style={{ height: "100vh" }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
          background: themeToken.colorBgContainer,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* 菜单导航（会话列表已不在侧边栏展示，聊天入口走 /chat 智能体选择页） */}
        <div style={{ flex: 1, overflow: "auto" }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ borderInlineEnd: "none" }}
          />
        </div>

        {/* 退出登录 */}
        <div style={{ borderTop: `1px solid ${themeToken.colorBorderSecondary}` }}>
          <div
            style={{
              padding: "8px 16px",
              borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
            }}
          >
            <Button
              icon={<LogoutOutlined />}
              onClick={() => {
                logout();
                navigate("/login");
              }}
              type="text"
              danger
              block
            >
              {!collapsed && "退出登录"}
            </Button>
          </div>
        </div>
      </Sider>

      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: themeToken.colorBgContainer,
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <div style={{ color: themeToken.colorTextSecondary, fontSize: 14 }}>
            {user?.username}
            {isAdmin && (
              <span
                style={{
                  marginLeft: 8,
                  padding: "2px 8px",
                  background: themeToken.colorPrimaryBg,
                  borderRadius: 4,
                  fontSize: 12,
                  color: themeToken.colorPrimary,
                }}
              >
                管理员
              </span>
            )}
          </div>
        </Header>

        <Content
          style={{
            background: themeToken.colorBgLayout,
            overflow: "auto",
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
