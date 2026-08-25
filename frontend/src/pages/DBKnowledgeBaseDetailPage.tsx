/** 知识库详情（B 类·数据库型）— 表信息 + 知识点 两个 Tab
 *  复刻参考图：表列表（表名/注释/列数/必选/状态）+ 编辑表信息弹窗（字段信息表） */

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
  Switch,
  Popconfirm,
  message,
  Typography,
  Tabs,
  Tooltip,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
  DatabaseOutlined,
  ApiOutlined,
  SyncOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { KnowledgeBaseItem } from "../types/kb";
import type {
  DBTableItem,
  DBTableFieldItem,
  DBKnowledgePoint,
  DBKnowledgePointForm,
} from "../types/dbkb";
import {
  listTables,
  syncTables,
  updateTable,
  deleteTable,
  updateField,
  deleteField,
  listKnowledgePoints,
  createKnowledgePoint,
  updateKnowledgePoint,
  deleteKnowledgePoint,
} from "../api/kbTables";

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Props {
  kb: KnowledgeBaseItem;
  onChanged?: () => void;
}

const DBKnowledgeBaseDetailPage: React.FC<Props> = ({ kb, onChanged }) => {
  const [tables, setTables] = useState<DBTableItem[]>([]);
  const [tableLoading, setTableLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  // 编辑表信息弹窗
  const [tableModalOpen, setTableModalOpen] = useState(false);
  const [editingTable, setEditingTable] = useState<DBTableItem | null>(null);
  const [tableForm] = Form.useForm();
  // 知识点
  const [kps, setKps] = useState<DBKnowledgePoint[]>([]);
  const [kpTotal, setKpTotal] = useState(0);
  const [kpPage, setKpPage] = useState(1);
  const [kpLoading, setKpLoading] = useState(false);
  const [kpModalOpen, setKpModalOpen] = useState(false);
  const [editingKp, setEditingKp] = useState<DBKnowledgePoint | null>(null);
  const [kpSaving, setKpSaving] = useState(false);
  const [kpForm] = Form.useForm<DBKnowledgePointForm>();

  const fetchTables = useCallback(async () => {
    setTableLoading(true);
    try {
      setTables(await listTables(kb.id));
    } catch {
      message.error("获取表信息失败");
    }
    setTableLoading(false);
  }, [kb.id]);

  const fetchKps = useCallback(async () => {
    setKpLoading(true);
    try {
      const resp = await listKnowledgePoints(kb.id, kpPage, 20);
      setKps(resp.items);
      setKpTotal(resp.total);
    } catch {
      message.error("获取知识点列表失败");
    }
    setKpLoading(false);
  }, [kb.id, kpPage]);

  useEffect(() => {
    fetchTables();
    fetchKps();
  }, [fetchTables, fetchKps]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const resp = await syncTables(kb.id);
      message.success(resp.message);
      fetchTables();
      onChanged?.();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || "同步失败");
    }
    setSyncing(false);
  };

  const openEditTable = (t: DBTableItem) => {
    setEditingTable(t);
    tableForm.resetFields();
    tableForm.setFieldsValue({ table_comment: t.table_comment, is_required: t.is_required });
    setTableModalOpen(true);
  };

  const handleTableSave = async () => {
    try {
      const values = await tableForm.validateFields();
      await updateTable(kb.id, editingTable!.id, {
        table_comment: values.table_comment,
        is_required: values.is_required,
      });
      message.success("表信息已更新");
      setTableModalOpen(false);
      fetchTables();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "保存失败");
    }
  };

  const handleFieldUpdate = async (field: DBTableFieldItem, patch: { field_comment?: string; is_required?: boolean }) => {
    try {
      await updateField(kb.id, field.db_table_id, field.id, patch);
      fetchTables();
    } catch {
      message.error("字段更新失败");
    }
  };

  const handleFieldDelete = async (field: DBTableFieldItem) => {
    try {
      await deleteField(kb.id, field.db_table_id, field.id);
      message.success("字段已删除");
      fetchTables();
    } catch {
      message.error("删除失败");
    }
  };

  const handleTableDelete = async (t: DBTableItem) => {
    try {
      await deleteTable(kb.id, t.id);
      message.success("表已删除");
      fetchTables();
      onChanged?.();
    } catch {
      message.error("删除失败");
    }
  };

  const openCreateKp = () => {
    setEditingKp(null);
    kpForm.resetFields();
    setKpModalOpen(true);
  };

  const openEditKp = (kp: DBKnowledgePoint) => {
    setEditingKp(kp);
    kpForm.setFieldsValue({ name: kp.name, content: kp.content });
    setKpModalOpen(true);
  };

  const handleKpSubmit = async () => {
    try {
      const values = await kpForm.validateFields();
      setKpSaving(true);
      if (editingKp) {
        await updateKnowledgePoint(kb.id, editingKp.id, values);
        message.success("知识点已更新");
      } else {
        await createKnowledgePoint(kb.id, values);
        message.success("知识点已新增");
      }
      setKpModalOpen(false);
      fetchKps();
      onChanged?.();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "保存失败");
    }
    setKpSaving(false);
  };

  const handleKpDelete = async (kp: DBKnowledgePoint) => {
    try {
      await deleteKnowledgePoint(kb.id, kp.id);
      message.success("知识点已删除");
      fetchKps();
      onChanged?.();
    } catch {
      message.error("删除失败");
    }
  };

  const fieldColumns: ColumnsType<DBTableFieldItem> = [
    { title: "字段名称", dataIndex: "field_name", render: (v: string) => <Text code>{v}</Text> },
    { title: "类型", dataIndex: "field_type", width: 140, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: "字段描述（给 AI 看）",
      dataIndex: "field_comment",
      ellipsis: true,
      render: (v: string, record) => (
        <Input
          size="small"
          defaultValue={v}
          placeholder="补充字段业务含义（源库有注释会自动填入）"
          onBlur={(e) => {
            if (e.target.value !== v) handleFieldUpdate(record, { field_comment: e.target.value });
          }}
          style={{ maxWidth: 320 }}
        />
      ),
    },
    {
      title: "必带",
      dataIndex: "is_required",
      width: 70,
      render: (v: boolean, record) => (
        <Switch
          size="small"
          checked={v}
          onChange={(checked) => handleFieldUpdate(record, { is_required: checked })}
        />
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (s: string) =>
        s === "conflict" ? <Tag color="red">①冲突</Tag> : <Tag color="success">正常</Tag>,
    },
    {
      title: "操作",
      key: "actions",
      width: 70,
      render: (_, record) => (
        <Popconfirm title="删除该字段？" onConfirm={() => handleFieldDelete(record)}>
          <Button type="text" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const tableColumns: ColumnsType<DBTableItem> = [
    {
      title: "表名",
      dataIndex: "table_name",
      render: (v: string) => <Text strong><DatabaseOutlined /> {v}</Text>,
    },
    { title: "表描述", dataIndex: "table_comment", ellipsis: true, render: (v: string) => v || "-" },
    { title: "列数", dataIndex: "column_count", width: 70 },
    {
      title: "必选",
      dataIndex: "is_required",
      width: 70,
      render: (v: boolean) => (v ? <Tag color="blue">启用</Tag> : <Tag>关闭</Tag>),
    },
    {
      title: "状态",
      dataIndex: "status",
      width: 90,
      render: (s: string) =>
        s === "conflict" ? <Tag color="red">①冲突</Tag> : <Tag color="success">正常</Tag>,
    },
    {
      title: "创建日期",
      dataIndex: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 140,
      render: (_, record) => (
        <Space>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditTable(record)}>
            编辑
          </Button>
          <Popconfirm title="删除该表及其字段记录？" onConfirm={() => handleTableDelete(record)}>
            <Button type="text" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const kpColumns: ColumnsType<DBKnowledgePoint> = [
    { title: "名称", dataIndex: "name", render: (v: string) => <b><BulbOutlined /> {v}</b> },
    { title: "内容", dataIndex: "content", ellipsis: true, render: (v: string) => <Text type="secondary">{v}</Text> },
    {
      title: "录入时间",
      dataIndex: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 130,
      render: (_, record) => (
        <Space>
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditKp(record)}>
            编辑
          </Button>
          <Popconfirm title="删除该知识点？" onConfirm={() => handleKpDelete(record)}>
            <Button type="text" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Text type="secondary">
          <ApiOutlined /> 数据源: {kb.data_source_name || kb.data_source_id} / 库: {kb.database_name}
        </Text>
        <Button size="small" icon={<SyncOutlined />} onClick={handleSync} loading={syncing}>
          同步表结构
        </Button>
      </Space>

      <Tabs
        defaultActiveKey="tables"
        items={[
          {
            key: "tables",
            label: (
              <span>
                <DatabaseOutlined /> 表信息（{tables.length}）
              </span>
            ),
            children: (
              <Card
                size="small"
                title="库中表清单（自动同步自源库，字段描述可人工维护）"
                extra={
                  <Button size="small" icon={<ReloadOutlined />} onClick={fetchTables} loading={tableLoading}>
                    刷新
                  </Button>
                }
              >
                <Table
                  columns={tableColumns}
                  dataSource={tables}
                  rowKey="id"
                  loading={tableLoading}
                  size="middle"
                  scroll={{ x: "max-content" }}
                  pagination={false}
                  expandable={{
                    expandedRowRender: (record) => (
                      <Table
                        columns={fieldColumns}
                        dataSource={record.fields}
                        rowKey="id"
                        size="small"
                        scroll={{ x: "max-content" }}
                        pagination={false}
                        title={() => (
                          <Space size={8}>
                            <Text strong>字段信息（{record.fields.length}）</Text>
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              修改描述后移出输入框自动保存
                            </Text>
                          </Space>
                        )}
                      />
                    ),
                  }}
                />
              </Card>
            ),
          },
          {
            key: "kps",
            label: (
              <span>
                <BulbOutlined /> 知识点（{kpTotal}）
              </span>
            ),
            children: (
              <Card
                size="small"
                extra={
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreateKp}>
                    录入信息
                  </Button>
                }
              >
                <Table
                  columns={kpColumns}
                  dataSource={kps}
                  rowKey="id"
                  loading={kpLoading}
                  size="middle"
                  scroll={{ x: "max-content" }}
                  pagination={{
                    current: kpPage,
                    pageSize: 20,
                    total: kpTotal,
                    onChange: setKpPage,
                    showTotal: (t) => `共 ${t} 条知识点`,
                    showSizeChanger: false,
                  }}
                />
              </Card>
            ),
          },
        ]}
      />

      {/* 编辑表信息弹窗（复刻参考图：选表 + 必选开关 + 表描述 + 字段信息表） */}
      <Modal
        title="编辑表信息"
        open={tableModalOpen}
        onCancel={() => setTableModalOpen(false)}
        onOk={handleTableSave}
        width={760}
        footer={[
          <Button key="cancel" onClick={() => setTableModalOpen(false)}>取消</Button>,
          <Button key="ok" type="primary" onClick={handleTableSave}>确定</Button>,
        ]}
      >
        {editingTable && (
          <Form form={tableForm} layout="vertical" requiredMark={false} style={{ marginTop: 8 }}>
            <Space.Compact block style={{ display: "flex", gap: 8 }}>
              <Form.Item label="表名" style={{ flex: 1 }}>
                <Input value={editingTable.table_name} disabled />
              </Form.Item>
              <Form.Item name="is_required" label="必选" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Space.Compact>
            <Form.Item name="table_comment" label="表描述">
              <Input placeholder="这张表存储着什么？给 AI 看的说明" maxLength={500} />
            </Form.Item>
          </Form>
        )}
        <Table
          columns={fieldColumns}
          dataSource={editingTable?.fields || []}
          rowKey="id"
          size="small"
          scroll={{ x: "max-content" }}
          pagination={false}
          title={() => <Text strong>字段信息（{editingTable?.fields.length || 0}）</Text>}
        />
      </Modal>

      {/* 知识点录入弹窗 */}
      <Modal
        title={editingKp ? "编辑知识点" : "录入信息"}
        open={kpModalOpen}
        onCancel={() => setKpModalOpen(false)}
        onOk={handleKpSubmit}
        confirmLoading={kpSaving}
        width={560}
      >
        <Form form={kpForm} layout="vertical" requiredMark={false} style={{ marginTop: 8 }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
            <Input placeholder="如：数据有效性" maxLength={255} />
          </Form.Item>
          <Form.Item name="content" label="内容" rules={[{ required: true, message: "请输入内容" }]}>
            <TextArea placeholder="补充说明库/表/字段的业务语义，提升 AI 生成 SQL 的准确率" rows={5} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default DBKnowledgeBaseDetailPage;
