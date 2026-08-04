/** 个人中心页面 — 修改密码 */

import React, { useState } from "react";
import { Card, Form, Input, Button, Typography, Alert, Descriptions, theme, Divider } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { changePassword } from "../api/auth";

const { Title, Text } = Typography;

const ProfilePage: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form] = Form.useForm();
  const { token: themeToken } = theme.useToken();

  const handleChangePassword = async (values: {
    old_password: string;
    new_password: string;
    confirm_new_password: string;
  }) => {
    setError(null);
    setSuccess(null);
    setLoading(true);
    try {
      await changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
        confirm_new_password: values.confirm_new_password,
      });
      setSuccess("密码修改成功，请使用新密码重新登录");
      form.resetFields();
      setTimeout(() => {
        logout();
        navigate("/login");
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "密码修改失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 600, margin: "0 auto" }}>
      <Title level={4}>
        <UserOutlined /> 个人中心
      </Title>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="用户名">{user?.username}</Descriptions.Item>
          <Descriptions.Item label="角色">
            {user?.role === "admin" ? "管理员" : "普通用户"}
          </Descriptions.Item>
          <Descriptions.Item label="注册时间">
            {user?.created_at ? new Date(user.created_at).toLocaleString("zh-CN") : "-"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Divider />

      <Title level={5}>修改密码</Title>

      {error && (
        <Alert message={error} type="error" showIcon closable style={{ marginBottom: 16 }} onClose={() => setError(null)} />
      )}
      {success && (
        <Alert message={success} type="success" showIcon style={{ marginBottom: 16 }} />
      )}

      <Form form={form} onFinish={handleChangePassword} size="large" layout="vertical">
        <Form.Item
          name="old_password"
          label="旧密码"
          rules={[{ required: true, message: "请输入旧密码" }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="输入旧密码" />
        </Form.Item>
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 6, message: "密码至少 6 个字符" },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="输入新密码（至少6位）" />
        </Form.Item>
        <Form.Item
          name="confirm_new_password"
          label="确认新密码"
          dependencies={["new_password"]}
          rules={[
            { required: true, message: "请确认新密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("new_password") === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error("两次密码不一致"));
              },
            }),
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="再次输入新密码" />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            修改密码
          </Button>
        </Form.Item>
      </Form>
    </div>
  );
};

export default ProfilePage;
