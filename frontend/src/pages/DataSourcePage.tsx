/** 数据源管理页面 — 仅管理员可访问（列表 + 新建/编辑弹窗 + 连通测试） */

import React, { useEffect, useState, useCallback } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  Popconfirm,
  message,
  Typography,
  InputNumber,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ApiOutlined,
  DatabaseOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { DataSourceItem, DataSourceForm } from "../types/datasource";
import {
  listDataSources,
  createDataSource,
  updateDataSource,
  deleteDataSource,
  testDataSourceConnection,
} from "../api/datasources";

const { Title } = Typography;

const DataSourcePage: React.FC = () => {
  const [items, setItems] = useState<DataSourceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<DataSourceItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form] = Form.useForm<DataSourceForm>();

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listDataSources();
      setItems(data);
    } catch {
      message.error("获取数据源列表失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ type: "mysql", port: 3306 });
    setModalOpen(true);
  };

  const openEdit = (record: DataSourceItem) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      host: record.host,
      port: record.port,
      database: record.database,
      username: record.username,
      password: "", // 密码不回显，留空表示不修改
    });
    setModalOpen(true);
  };

  const handleTest = async () => {
    try {
      const values = await form.validateFields();
      setTesting(true);
      const resp = await testDataSourceConnection(values);
      if (resp.success) {
        message.success(`连接成功${resp.latency_ms != null ? `（${resp.latency_ms}ms）` : ""}`);
      } else {
        Modal.error({
          title: "连接失败",
          width: 480,
          content: (
            <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 13 }}>
              {resp.message}
            </div>
          ),
        });
      }
    } catch (err: any) {
      if (err?.errorFields) {
        message.warning("请先填写完整的连接信息再检测");
      } else {
        message.error(err?.response?.data?.detail || "检测失败");
      }
    }
    setTesting(false);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editing) {
        const payload: Partial<DataSourceForm> = { ...values };
        if (!payload.password) delete payload.password; // 空密码 = 不修改
        await updateDataSource(editing.id, payload);
        message.success("数据源已更新");
      } else {
        await createDataSource(values);
        message.success("数据源已创建");
      }
      setModalOpen(false);
      fetchList();
    } catch (err: any) {
      if (err?.errorFields) return; // 表单校验失败，静默
      message.error(err?.response?.data?.detail || "保存失败");
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDataSource(id);
      message.success("数据源已删除");
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "删除失败");
    }
  };

  const columns: ColumnsType<DataSourceItem> = [
    { title: "ID", dataIndex: "id", width: 60 },
    {
      title: "数据源名称",
      dataIndex: "name",
      render: (name: string) => <Space><DatabaseOutlined style={{ color: "#1677ff" }} /><b>{name}</b></Space>,
    },
    {
      title: "类型",
      dataIndex: "type",
      width: 90,
      render: (t: string) => <Tag color="blue">{t.toUpperCase()}</Tag>,
    },
    { title: "地址", dataIndex: "host", width: 140 },
    { title: "端口", dataIndex: "port", width: 80 },
    { title: "库/服务名", dataIndex: "database", width: 140 },
    { title: "用户名", dataIndex: "username", width: 100 },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_, record) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此数据源？"
            description="删除后无法恢复；已被知识库引用的数据源会被拒绝删除。"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          <DatabaseOutlined /> 数据源管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建数据源
        </Button>
      </div>

      <Card
        size="small"
        title="数据库连接列表"
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} size="small" onClick={fetchList}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          size="middle"
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个数据源` }}
        />
      </Card>

      <Modal
        title={editing ? "编辑数据源" : "新建数据源"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saving}
        width={520}
        footer={[
          <Button key="test" icon={<ApiOutlined />} onClick={handleTest} loading={testing}>
            检测
          </Button>,
          <Button key="cancel" onClick={() => setModalOpen(false)}>
            取消
          </Button>,
          <Button key="ok" type="primary" onClick={handleSubmit} loading={saving}>
            确定
          </Button>,
        ]}
      >
        <Form form={form} layout="vertical" requiredMark={false} style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="数据源名称"
            rules={[{ required: true, message: "请输入数据源名称" }]}
          >
            <Input placeholder="如 mysql51（自取别名，仅作代号）" maxLength={100} />
          </Form.Item>

          <Form.Item name="type" label="类型" initialValue="mysql">
            <Select
              options={[{ label: "MySQL", value: "mysql" }]}
              disabled={!!editing} // 当前仅支持 mysql，编辑时不可改
            />
          </Form.Item>

          <Space.Compact block style={{ display: "flex", gap: 8 }}>
            <Form.Item
              name="host"
              label="地址"
              style={{ flex: 1 }}
              rules={[{ required: true, message: "请输入地址" }]}
            >
              <Input placeholder="如 192.168.1.51" />
            </Form.Item>
            <Form.Item name="port" label="端口" initialValue={3306} style={{ width: 110 }}>
              <InputNumber min={1} max={65535} style={{ width: "100%" }} />
            </Form.Item>
          </Space.Compact>

          <Form.Item
            name="database"
            label="库/服务名"
            rules={[{ required: true, message: "请输入库/服务名" }]}
          >
            <Input placeholder="数据库中真实存在的库名，如 ods" />
          </Form.Item>

          <Space.Compact block style={{ display: "flex", gap: 8 }}>
            <Form.Item
              name="username"
              label="用户名"
              style={{ flex: 1 }}
              rules={[{ required: true, message: "请输入用户名" }]}
            >
              <Input placeholder="如 root" />
            </Form.Item>
            <Form.Item
              name="password"
              label="密码"
              style={{ flex: 1 }}
              rules={
                editing
                  ? []
                  : [{ required: true, message: "请输入密码" }]
              }
              extra={editing ? "留空表示不修改密码" : undefined}
            >
              <Input.Password placeholder="如 123456" />
            </Form.Item>
          </Space.Compact>
        </Form>
      </Modal>
    </div>
  );
};

export default DataSourcePage;
