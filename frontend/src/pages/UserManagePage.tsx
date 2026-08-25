/** 管理员：用户管理页面 — 列表 / 新建 / 启用禁用 / 重置密码 / 删除 */

import React, { useEffect, useState } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Switch,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  message,
  theme,
} from "antd";
import {
  PlusOutlined,
  KeyOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import {
  listAdminUsers,
  createAdminUser,
  updateAdminUser,
  resetUserPassword,
  deleteAdminUser,
  type AdminUserItem,
} from "../api/users";
import { useAuthStore } from "../store/authStore";

const UserManagePage: React.FC = () => {
  const { token: themeToken } = theme.useToken();
  const currentUser = useAuthStore((s) => s.user);

  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [loading, setLoading] = useState(false);

  // 新建用户弹窗
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [creating, setCreating] = useState(false);

  // 重置密码弹窗
  const [resetTarget, setResetTarget] = useState<AdminUserItem | null>(null);
  const [resetForm] = Form.useForm();
  const [resetting, setResetting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setUsers(await listAdminUsers());
    } catch {
      message.error("加载用户列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleToggleActive = async (user: AdminUserItem, checked: boolean) => {
    try {
      await updateAdminUser(user.id, { is_active: checked });
      message.success(checked ? `已启用「${user.username}」` : `已禁用「${user.username}」`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "操作失败");
    }
  };

  const handleCreate = async () => {
    const values = await createForm.validateFields();
    setCreating(true);
    try {
      await createAdminUser(values);
      message.success("用户创建成功");
      setCreateOpen(false);
      createForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetTarget) return;
    const values = await resetForm.validateFields();
    setResetting(true);
    try {
      await resetUserPassword(resetTarget.id, values.new_password);
      message.success(`已重置「${resetTarget.username}」的密码`);
      setResetTarget(null);
      resetForm.resetFields();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "重置失败");
    } finally {
      setResetting(false);
    }
  };

  const handleDelete = async (user: AdminUserItem) => {
    try {
      await deleteAdminUser(user.id);
      message.success(`已删除「${user.username}」`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  };

  const columns: ColumnsType<AdminUserItem> = [
    {
      title: "ID",
      dataIndex: "id",
      width: 70,
    },
    {
      title: "用户名",
      dataIndex: "username",
      render: (v: string, record) => (
        <Space size={6}>
          <span style={{ fontWeight: 500 }}>{v}</span>
          {record.id === currentUser?.id && <Tag color="blue">当前</Tag>}
        </Space>
      ),
    },
    {
      title: "角色",
      dataIndex: "role",
      width: 120,
      render: (v: string) =>
        v === "admin" ? (
          <Tag color="red">管理员</Tag>
        ) : (
          <Tag color="default">普通用户</Tag>
        ),
    },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 120,
      render: (v: boolean) =>
        v ? <Tag color="green">启用</Tag> : <Tag color="default">禁用</Tag>,
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 200,
      render: (v: string) => (v ? v.replace("T", " ").slice(0, 19) : "-"),
    },
    {
      title: "启用 / 禁用",
      width: 110,
      render: (_, record) => (
        <Switch
          checked={record.is_active}
          disabled={record.id === currentUser?.id}
          onChange={(checked) => handleToggleActive(record, checked)}
        />
      ),
    },
    {
      title: "操作",
      width: 220,
      render: (_, record) => (
        <Space size={4}>
          <Button
            type="link"
            size="small"
            icon={<KeyOutlined />}
            onClick={() => {
              setResetTarget(record);
              resetForm.resetFields();
            }}
          >
            重置密码
          </Button>
          <Popconfirm
            title={`确认删除用户「${record.username}」？`}
            description="将同时删除其会话等关联数据"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            disabled={record.id === currentUser?.id}
            onConfirm={() => handleDelete(record)}
          >
            <Button
              type="link"
              size="small"
              danger
              disabled={record.id === currentUser?.id}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Card
        title="用户管理"
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateOpen(true);
              createForm.resetFields();
            }}
          >
            新建用户
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={users}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ x: "max-content" }}
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个用户` }}
        />
      </Card>

      {/* 新建用户 */}
      <Modal
        title="新建用户"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        confirmLoading={creating}
        okText="创建"
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { pattern: /^[a-zA-Z0-9_]+$/, message: "只能包含字母、数字和下划线" },
              { min: 3, message: "至少 3 个字符" },
            ]}
          >
            <Input placeholder="如：zhangsan" prefix={<UserAddOutlined />} />
          </Form.Item>
          <Form.Item
            name="password"
            label="初始密码"
            rules={[
              { required: true, message: "请输入初始密码" },
              { min: 6, message: "至少 6 位" },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="user">
            <Select
              options={[
                { value: "user", label: "普通用户" },
                { value: "admin", label: "管理员" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重置密码 */}
      <Modal
        title={`重置「${resetTarget?.username ?? ""}」的密码`}
        open={!!resetTarget}
        onCancel={() => setResetTarget(null)}
        onOk={handleResetPassword}
        confirmLoading={resetting}
        okText="重置"
      >
        <Form form={resetForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: "请输入新密码" },
              { min: 6, message: "至少 6 位" },
            ]}
          >
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagePage;
