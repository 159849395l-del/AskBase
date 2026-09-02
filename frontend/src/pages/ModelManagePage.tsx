/** 大模型库管理页面 — 仅管理员（列表 + 新建/编辑弹窗 + 连通测试） */

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
  Switch,
  Popconfirm,
  message,
  Typography,
  InputNumber,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  BulbOutlined,
  ApiOutlined,
  StarOutlined,
  StarFilled,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type {
  LLMModelItem,
  LLMModelForm,
  ProviderOption,
} from "../types/llmModel";
import { PROVIDER_LABELS } from "../types/llmModel";
import {
  listModels,
  createModel,
  updateModel,
  deleteModel,
  testModel,
  setDefaultModel,
  listProviders,
} from "../api/models";

const { Title } = Typography;

const ModelManagePage: React.FC = () => {
  const [items, setItems] = useState<LLMModelItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<LLMModelItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [providers, setProviders] = useState<ProviderOption[]>([]);
  const [form] = Form.useForm<LLMModelForm>();

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listModels());
    } catch {
      message.error("获取模型列表失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchList();
    listProviders()
      .then(setProviders)
      .catch(() => {});
  }, [fetchList]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      provider: "deepseek",
      is_active: true,
      is_vision: false,
      supports_tool_call: false,
      temperature: 0.3,
      sort_order: 0,
      is_default: false,
    });
    setModalOpen(true);
  };

  const openEdit = (record: LLMModelItem) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      provider: record.provider,
      model_id: record.model_id,
      base_url: record.base_url,
      api_key: "",
      is_active: record.is_active,
      is_vision: record.is_vision,
      supports_tool_call: record.supports_tool_call,
      temperature: record.temperature,
      max_tokens: record.max_tokens,
      sort_order: record.sort_order,
      is_default: record.is_default,
    });
    setModalOpen(true);
  };

  const handleTest = async () => {
    if (!editing) {
      message.warning("请先保存模型再测试连通性");
      return;
    }
    setTesting(true);
    try {
      const resp = await testModel(editing.id);
      if (resp.success) {
        message.success(resp.message);
      } else {
        Modal.error({
          title: "连通失败",
          width: 520,
          content: (
            <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 13 }}>
              {resp.message}
            </div>
          ),
        });
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "测试失败");
    }
    setTesting(false);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editing) {
        const payload: Partial<LLMModelForm> = { ...values };
        if (!payload.api_key) delete payload.api_key; // 空密钥 = 不修改
        await updateModel(editing.id, payload);
        message.success("模型已更新");
      } else {
        await createModel(values);
        message.success("模型已创建");
      }
      setModalOpen(false);
      fetchList();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "保存失败");
    }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteModel(id);
      message.success("模型已删除");
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "删除失败");
    }
  };

  const handleSetDefault = async (id: number) => {
    try {
      await setDefaultModel(id);
      message.success("已设为系统默认模型");
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "设置失败");
    }
  };

  const columns: ColumnsType<LLMModelItem> = [
    { title: "ID", dataIndex: "id", width: 56 },
    {
      title: "模型名称",
      dataIndex: "name",
      render: (name: string, record) => (
        <Space>
          <BulbOutlined style={{ color: "#1677ff" }} />
          <b>{name}</b>
          {record.is_default && <Tag color="gold">默认</Tag>}
        </Space>
      ),
    },
    {
      title: "厂商",
      dataIndex: "provider",
      width: 150,
      render: (p: string) => (
        <Tag color="blue">{PROVIDER_LABELS[p] || p}</Tag>
      ),
    },
    { title: "模型 ID", dataIndex: "model_id", width: 180, ellipsis: true },
    {
      title: "接口地址",
      dataIndex: "base_url",
      width: 220,
      ellipsis: true,
      render: (u: string) => (
        <Tooltip title={u}>
          <span>{u}</span>
        </Tooltip>
      ),
    },
    {
      title: "能力",
      key: "caps",
      width: 150,
      render: (_, record) => (
        <Space size={4}>
          {record.is_vision && <Tag color="purple">视觉</Tag>}
          {record.supports_tool_call && <Tag color="cyan">工具调用</Tag>}
          {!record.is_vision && !record.supports_tool_call && (
            <span style={{ color: "#999" }}>—</span>
          )}
        </Space>
      ),
    },
    {
      title: "状态",
      dataIndex: "is_active",
      width: 90,
      render: (active: boolean) => (
        <Tag color={active ? "green" : "default"}>{active ? "启用" : "停用"}</Tag>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 220,
      render: (_, record) => (
        <Space size={4}>
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Tooltip title={record.is_default ? "已是默认模型" : "设为系统默认"}>
            <Button
              type="text"
              size="small"
              icon={record.is_default ? <StarFilled /> : <StarOutlined />}
              disabled={record.is_default}
              onClick={() => handleSetDefault(record.id)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除此模型？"
            description="删除后无法恢复；引用它的智能体会自动改用系统默认模型。"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="text" danger size="small" icon={<DeleteOutlined />} />
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
          <BulbOutlined /> 大模型库
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增模型
        </Button>
      </div>

      <Card
        size="small"
        title="模型列表"
        extra={
          <Button icon={<ReloadOutlined />} size="small" onClick={fetchList}>
            刷新
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          size="middle"
          scroll={{ x: "max-content" }}
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个模型` }}
        />
      </Card>

      <Modal
        title={editing ? "编辑模型" : "新增模型"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saving}
        width={560}
        footer={[
          <Button
            key="test"
            icon={<ApiOutlined />}
            onClick={handleTest}
            loading={testing}
            disabled={!editing}
          >
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
            name="provider"
            label="厂商名称"
            rules={[{ required: true, message: "请选择厂商" }]}
          >
            <Select
              placeholder="选择厂商"
              options={providers.map((p) => ({ label: p.label, value: p.value }))}
              onChange={(v) => {
                const hit = providers.find((p) => p.value === v);
                if (hit?.default_base_url) {
                  form.setFieldValue("base_url", hit.default_base_url);
                }
              }}
            />
          </Form.Item>

          <Form.Item
            name="name"
            label="模型名称"
            rules={[{ required: true, message: "请输入模型名称" }]}
          >
            <Input placeholder="如：DeepSeek V3（展示用名称）" maxLength={100} />
          </Form.Item>

          <Form.Item
            name="model_id"
            label="模型 ID"
            rules={[{ required: true, message: "请输入模型 ID" }]}
            extra="必须与厂商实际提供的模型标识完全一致（含大小写与后缀）"
          >
            <Input placeholder="如：deepseek-chat" maxLength={100} />
          </Form.Item>

          <Form.Item
            name="base_url"
            label="接口地址"
            rules={[{ required: true, message: "请输入接口地址" }]}
            extra="OpenAI 兼容端点，选择厂商后自动填充，可修改"
          >
            <Input placeholder="如：https://api.deepseek.com" />
          </Form.Item>

          <Form.Item
            name="api_key"
            label="API Key"
            rules={editing ? [] : [{ required: true, message: "请输入 API Key" }]}
            extra={editing ? "留空表示不修改密钥" : undefined}
          >
            <Input.Password placeholder="sk-..." autoComplete="new-password" />
          </Form.Item>

          <Space size={16} wrap>
            <Form.Item name="is_active" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item name="is_vision" label="视觉模型" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item
              name="supports_tool_call"
              label="支持工具调用"
              valuePropName="checked"
              extra="关闭时该模型不会触发 Skill / MCP 工具"
            >
              <Switch />
            </Form.Item>
          </Space>

          <Space size={16} wrap>
            <Form.Item name="temperature" label="默认温度" style={{ width: 120 }}>
              <InputNumber min={0} max={2} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="max_tokens" label="最大输出 Token" style={{ width: 160 }}>
              <InputNumber min={1} placeholder="不限" style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="sort_order" label="排序" style={{ width: 110 }}>
              <InputNumber min={0} style={{ width: "100%" }} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
};

export default ModelManagePage;
