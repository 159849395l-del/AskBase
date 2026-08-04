/** 注册页面 */

import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, Alert, theme } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

const { Title, Text } = Typography;

const RegisterPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const register = useAuthStore((s) => s.register);
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();

  const onFinish = async (values: {
    username: string;
    password: string;
    confirm_password: string;
  }) => {
    setError(null);
    setLoading(true);
    try {
      await register(values.username, values.password, values.confirm_password);
      setSuccess(true);
      setTimeout(() => navigate("/login"), 1500);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join("; "));
      } else {
        setError(detail || err.message || "注册失败");
      }
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
            注册新账号
          </Title>
          <Text type="secondary">创建账号后即可使用知识库问答</Text>
        </div>

        {error && (
          <Alert message={error} type="error" showIcon closable style={{ marginBottom: 16 }} onClose={() => setError(null)} />
        )}
        {success && (
          <Alert message="注册成功！即将跳转到登录页..." type="success" showIcon style={{ marginBottom: 16 }} />
        )}

        <Form name="register" onFinish={onFinish} size="large">
          <Form.Item
            name="username"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, max: 50, message: "用户名长度 3-50 个字符" },
              { pattern: /^[a-zA-Z0-9_]+$/, message: "只能包含字母、数字和下划线" },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 6, message: "密码至少 6 个字符" },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码（至少6位）" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请确认密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error("两次密码不一致"));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block>
              注册
            </Button>
          </Form.Item>
        </Form>

        <div style={{ textAlign: "center" }}>
          <Text type="secondary">
            已有账号？<Link to="/login">立即登录</Link>
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default RegisterPage;
