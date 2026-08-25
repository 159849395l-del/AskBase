/** 知识库管理页面 — 仅管理员可访问（知识库列表 + 新建/编辑弹窗） */

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
  Radio,
  Popconfirm,
  message,
  Typography,
  Tooltip,
} from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  ApiOutlined,
  BookOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { KnowledgeBaseItem, KnowledgeBaseForm, UserBrief } from "../types/kb";
import { listKnowledgeBases, createKnowledgeBase, updateKnowledgeBase, deleteKnowledgeBase, listUsers } from "../api/knowledgeBases";
import { useNavigate } from "react-router-dom";
import type { DataSourceItem } from "../types/datasource";
import { listDataSources } from "../api/datasources";

const { Title } = Typography;
const { TextArea } = Input;

const KnowledgeBasePage: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<KnowledgeBaseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<KnowledgeBaseItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [dataSources, setDataSources] = useState<DataSourceItem[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [form] = Form.useForm<KnowledgeBaseForm>();
  const kbType = Form.useWatch("type", form) || "document";
  const selectedDsId = Form.useWatch("data_source_id", form);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listKnowledgeBases();
      setItems(data);
    } catch {
      message.error("获取知识库列表失败");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchList();
    listDataSources().then(setDataSources).catch(() => setDataSources([]));
    listUsers().then(setUsers).catch(() => setUsers([]));
  }, [fetchList]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ type: "document", label: "", description: "" });
    setModalOpen(true);
  };

  const openEdit = (record: KnowledgeBaseItem) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      label: record.label,
      authorized_user_id: record.authorized_user_id ?? null,
      type: record.type,
      data_source_id: record.data_source_id ?? null,
      database_name: record.database_name ?? "",
      description: record.description,
    });
    setModalOpen(true);
  };

  // 类型切换：清空数据源相关字段
  const handleTypeChange = (type: string) => {
    if (type === "document") {
      form.setFieldsValue({ data_source_id: null, database_name: "" });
    }
  };

  // 选择数据源后，库名默认带出该数据源的库/服务名（可改）
  const handleDsChange = (dsId: number | null) => {
    if (dsId) {
      const ds = dataSources.find((d) => d.id === dsId);
      if (ds) form.setFieldsValue({ database_name: ds.database });
    } else {
      form.setFieldsValue({ database_name: "" });
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: KnowledgeBaseForm = {
        name: values.name,
        label: values.label || "",
        authorized_user_id: values.authorized_user_id ?? null,
        type: values.type,
        description: values.description || "",
        data_source_id: null,
        database_name: undefined,
      };
      if (values.type === "database") {
        payload.data_source_id = values.data_source_id;
        payload.database_name = values.database_name?.trim();
      }
      if (editing) {
        await updateKnowledgeBase(editing.id, payload);
        message.success("知识库已更新");
      } else {
        await createKnowledgeBase(payload);
        message.success("知识库已创建");
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
      await deleteKnowledgeBase(id);
      message.success("知识库已删除");
      fetchList();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "删除失败");
    }
  };

  const columns: ColumnsType<KnowledgeBaseItem> = [
    { title: "ID", dataIndex: "id", width: 60 },
    {
      title: "知识库名称",
      dataIndex: "name",
      render: (name: string, record) => (
        <Space>
          {record.type === "document" ? (
            <BookOutlined style={{ color: "#0F6E56" }} />
          ) : (
            <DatabaseOutlined style={{ color: "#534AB7" }} />
          )}
          <b>{name}</b>
        </Space>
      ),
    },
    {
      title: "类型",
      dataIndex: "type",
      width: 110,
      render: (t: string) =>
        t === "database" ? (
          <Tag color="purple">数据库型</Tag>
        ) : (
          <Tag color="green">文档型</Tag>
        ),
    },
    {
      title: "数据源",
      dataIndex: "data_source_name",
      width: 120,
      render: (v: string | null, record) =>
        record.type === "database" ? (
          <Space size={4}>
            <ApiOutlined style={{ color: "#1677ff" }} />
            {v || record.data_source_id}
          </Space>
        ) : (
          "-"
        ),
    },
    {
      title: "库名",
      dataIndex: "database_name",
      width: 120,
      render: (v: string | null) => v || "-",
    },
    {
      title: "内容",
      key: "content",
      width: 170,
      render: (_, record) =>
        record.type === "document" ? (
          <Space size={4}>
            <FileTextOutlined />
            <span>{record.doc_count} 文档</span>
            <span style={{ color: "#999" }}>/</span>
            <span>{record.qa_count} 问答</span>
          </Space>
        ) : (
          <Space size={4}>
            <span>{record.table_count} 表</span>
            <span style={{ color: "#999" }}>/</span>
            <span>{record.kp_count} 知识点</span>
          </Space>
        ),
    },
    {
      title: "描述",
      dataIndex: "description",
      ellipsis: true,
      render: (v: string) => v || "-",
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
      width: 180,
      render: (_, record) => (
        <Space>
          <Button type="primary" size="small" ghost onClick={() => navigate(`/admin/kb/${record.id}`)}>
            管理内容
          </Button>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="确定删除此知识库？"
            description="其下文档/问答/表信息/知识点将一并删除。"
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <DatabaseOutlined /> 知识库管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建知识库
        </Button>
      </div>

      <Card
        size="small"
        title="知识库列表"
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
          pagination={{ pageSize: 10, showTotal: (t) => `共 ${t} 个知识库` }}
        />
      </Card>

      <Modal
        title={editing ? "编辑知识库" : "新建知识库"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        confirmLoading={saving}
        width={560}
      >
        <Form form={form} layout="vertical" requiredMark={false} style={{ marginTop: 8 }}>
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: "请输入知识库名称" }]}
          >
            <Input placeholder="如 高校新闻库" maxLength={100} />
          </Form.Item>

          <Space.Compact block style={{ display: "flex", gap: 8 }}>
            <Form.Item name="label" label="标签" style={{ flex: 1 }}>
              <Input placeholder="可选，如 新闻" maxLength={50} />
            </Form.Item>
            <Form.Item name="authorized_user_id" label="授权用户" style={{ flex: 1 }}>
              <Select
                allowClear
                placeholder="请选择用户"
                options={users.map((u) => ({
                  label: `${u.username}${u.role === "admin" ? "（管理员）" : ""}`,
                  value: u.id,
                }))}
              />
            </Form.Item>
          </Space.Compact>

          <Form.Item name="type" label="知识库类型" rules={[{ required: true }]}>
            <Radio.Group onChange={(e) => handleTypeChange(e.target.value)}>
              <Radio.Button value="document">文档型（无数据源）</Radio.Button>
              <Radio.Button value="database">数据库型（绑定数据源）</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {kbType === "database" && (
            <>
              <Form.Item label="知识库数据源">
                <Space.Compact block style={{ display: "flex", gap: 8 }}>
                  <Form.Item
                    name="data_source_id"
                    noStyle
                    rules={[{ required: true, message: "请选择数据源" }]}
                  >
                    <Select
                      placeholder="选择数据源"
                      style={{ width: "60%" }}
                      onChange={handleDsChange}
                      options={dataSources.map((d) => ({
                        label: `${d.name}（${d.host}:${d.port}）`,
                        value: d.id,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item
                    name="database_name"
                    noStyle
                    rules={[{ required: true, message: "请输入库名" }]}
                  >
                    <Input placeholder="库/服务名，如 ai_crawl" style={{ flex: 1 }} />
                  </Form.Item>
                </Space.Compact>
              </Form.Item>
              <Typography.Text type="secondary" style={{ fontSize: 12, display: "block", marginTop: -12, marginBottom: 8 }}>
                第一个框选择数据源，第二个框填写该数据库中的真实库名（默认带出数据源的库名，可改为同服务器其他库）
              </Typography.Text>
            </>
          )}

          <Form.Item name="description" label="知识库描述">
            <TextArea placeholder="可选，说明这个知识库的用途" rows={2} maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeBasePage;
