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
} from "@ant-design/icons";
import { useNavigate, useLocation, Outlet } from "react-router-dom";
import { useAuthStore } from "../../store/authStore";
import { useChatStore } from "../../store/chatStore";
import ConversationList from "./ConversationList";

const { Header, Sider, Content } = Layout;

const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((s) => s.logout);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const user = useAuthStore((s) => s.user);
  const fetchConversations = useChatStore((s) => s.fetchConversations);
  const resetChat = useChatStore((s) => s.reset);

  const { token: themeToken } = theme.useToken();

  useEffect(() => {
    // Reset chat store when user changes (different user logged in)
    resetChat();
    fetchConversations();
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
            key: "/admin/crawler/tasks",
            icon: <BugOutlined />,
            label: "爬虫管理",
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
        width={300}
        style={{
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
          background: themeToken.colorBgContainer,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* 会话列表（同一智能体复用同一会话，无需新建按钮） */}
        <div style={{ flex: 1, overflow: "auto" }}>
          <ConversationList collapsed={collapsed} />
        </div>

        {/* 菜单导航 */}
        <div style={{ borderTop: `1px solid ${themeToken.colorBorderSecondary}` }}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ borderInlineEnd: "none" }}
          />
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
