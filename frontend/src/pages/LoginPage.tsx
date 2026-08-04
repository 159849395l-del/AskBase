/** 登录页面 */

import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, Alert, theme } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();

  const onFinish = async (values: { username: string; password: string }) => {
    setError(null);
    setLoading(true);
    try {
      await login(values.username, values.password);
      navigate("/chat");
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: themeToken.colorBgLayout,
      }}
    >
      <Card
        style={{ width: 400, boxShadow: themeToken.boxShadow }}
        styles={{ body: { padding: "32px" } }}
      >
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Title level={3} style={{ marginBottom: 4 }}>
            电商 RAG 知识库问答系统
          </Title>
          <Text type="secondary">请登录以继续</Text>
        </div>

        {error && (
          <Alert message={error} type="error" showIcon closable style={{ marginBottom: 16 }} onClose={() => setError(null)} />
        )}

        <Form name="login" onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              登录
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: "center" }}>
          <Text type="secondary">
            还没有账号？<Link to="/register">立即注册</Link>
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default LoginPage;
