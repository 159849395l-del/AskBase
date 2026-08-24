/** 知识库详情页（A 类·文档型）— 问答集 + 文档集 两个 Tab */

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Upload,
  Modal,
  Form,
  Input,
  Popconfirm,
  message,
  Typography,
  Tabs,
  theme,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ArrowLeftOutlined,
  InboxOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { DocumentItem, KnowledgeBaseItem, QAItem, QAItemForm } from "../types/kb";
import { getKnowledgeBase } from "../api/knowledgeBases";
import { listDocuments, uploadDocument, deleteDocument, listQA, createQA, updateQA, deleteQA } from "../api/kb";
import DBKnowledgeBaseDetailPage from "./DBKnowledgeBaseDetailPage";

const { Title, Text } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  processing: { color: "processing", label: "处理中" },
  indexed: { color: "success", label: "已索引" },
  failed: { color: "error", label: "失败" },
};

const KnowledgeBaseDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const kbId = Number(id);
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();

  const [kb, setKb] = useState<KnowledgeBaseItem | null>(null);
  // 文档集
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [docTotal, setDocTotal] = useState(0);
  const [docPage, setDocPage] = useState(1);
  const [docLoading, setDocLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  // 问答集
  const [qaItems, setQaItems] = useState<QAItem[]>([]);
  const [qaTotal, setQaTotal] = useState(0);
  const [qaPage, setQaPage] = useState(1);
  const [qaLoading, setQaLoading] = useState(false);
  const [qaModalOpen, setQaModalOpen] = useState(false);
  const [editingQa, setEditingQa] = useState<QAItem | null>(null);
  const [qaSaving, setQaSaving] = useState(false);
  const [qaForm] = Form.useForm<QAItemForm>();

  const fetchKb = useCallback(async () => {
    try {
      setKb(await getKnowledgeBase(kbId));
    } catch {
      message.error("获取知识库详情失败");
    }
  }, [kbId]);

  const fetchDocs = useCallback(async () => {
    setDocLoading(true);
    try {
      const resp = await listDocuments(docPage, 20, undefined, kbId);
      setDocs(resp.items);
      setDocTotal(resp.total);
    } catch {
      message.error("获取文档列表失败");
    }
    setDocLoading(false);
  }, [kbId, docPage]);

  const fetchQA = useCallback(async () => {
    setQaLoading(true);
    try {
      const resp = await listQA(kbId, qaPage, 20);
      setQaItems(resp.items);
      setQaTotal(resp.total);
    } catch {
      message.error("获取问答列表失败");
    }
    setQaLoading(false);
  }, [kbId, qaPage]);

  useEffect(() => {
    fetchKb();
  }, [fetchKb]);
  useEffect(() => {
    if (kb?.type === "document") {
      fetchDocs();
      fetchQA();
    }
  }, [kb?.type, fetchDocs, fetchQA]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await uploadDocument(file, kbId);
      message.success(`文档 "${file.name}" 上传成功，正在后台向量化...`);
      fetchDocs();
      fetchKb();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "上传失败");
    }
    setUploading(false);
    return false;
  };

  const handleDeleteDoc = async (docId: number) => {
    try {
      await deleteDocument(docId);
      message.success("文档已删除");
      fetchDocs();
      fetchKb();
    } catch {
      message.error("删除失败");
    }
  };

  const openCreateQA = () => {
    setEditingQa(null);
    qaForm.resetFields();
    setQaModalOpen(true);
  };

  const openEditQA = (record: QAItem) => {
    setEditingQa(record);
    qaForm.setFieldsValue({ question: record.question, answer: record.answer });
    setQaModalOpen(true);
  };

  const handleQaSubmit = async () => {
    try {
      const values = await qaForm.validateFields();
      setQaSaving(true);
      if (editingQa) {
        await updateQA(editingQa.id, { question: values.question, answer: values.answer });
        message.success("问答已更新");
      } else {
        await createQA({ kb_id: kbId, question: values.question, answer: values.answer });
        message.success("问答已录入");
      }
      setQaModalOpen(false);
      fetchQA();
      fetchKb();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || "保存失败");
    }
    setQaSaving(false);
  };

  const handleDeleteQA = async (qaId: number) => {
    try {
      await deleteQA(qaId);
      message.success("问答已删除");
      fetchQA();
      fetchKb();
    } catch {
      message.error("删除失败");
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const docColumns: ColumnsType<DocumentItem> = [
    {
      title: "文件名",
      dataIndex: "filename",
      ellipsis: true,
      render: (name: string) => {
        const original = name.replace(/^[a-f0-9]+_/, "");
        return (
          <Space>
            <FileTextOutlined />
            <span title={original}>{original.length > 40 ? original.slice(0, 40) + "..." : original}</span>
          </Space>
        );
      },
    },
    { title: "类型", dataIndex: "file_type", width: 80, render: (t: string) => <Tag>{t.toUpperCase()}</Tag> },
    { title: "大小", dataIndex: "file_size", width: 100, render: (s: number) => formatFileSize(s) },
    { title: "块数", dataIndex: "chunk_count", width: 80 },
    {
      title: "状态",
      dataIndex: "status",
      width: 100,
      render: (s: string) => {
        const cfg = STATUS_MAP[s] || { color: "default", label: s };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: "上传时间",
      dataIndex: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_, record) => (
        <Popconfirm title="确定删除此文档？所有相关向量数据将被移除" onConfirm={() => handleDeleteDoc(record.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  const qaColumns: ColumnsType<QAItem> = [
    {
      title: "问题",
      dataIndex: "question",
      ellipsis: true,
      render: (q: string) => (
        <Space>
          <QuestionCircleOutlined style={{ color: "#1677ff" }} />
          <b>{q}</b>
        </Space>
      ),
    },
    {
      title: "答案",
      dataIndex: "answer",
      ellipsis: true,
      render: (a: string) => <Text type="secondary">{a}</Text>,
    },
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
          <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditQA(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此问答？" onConfirm={() => handleDeleteQA(record.id)}>
            <Button type="text" danger size="small" icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (!kb) return <div style={{ padding: 24 }}>加载中...</div>;

  // B 类（数据库型）→ 复用数据库型视图
  if (kb.type === "database") {
    return (
      <div style={{ padding: 24 }}>
        <Space style={{ marginBottom: 16 }} align="center">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/admin/kb")}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            <DatabaseOutlined /> {kb.name}
          </Title>
          <Tag color="purple">数据库型知识库</Tag>
          {kb.label && <Tag>{kb.label}</Tag>}
        </Space>
        {kb.description && (
          <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
            {kb.description}
          </Text>
        )}
        <DBKnowledgeBaseDetailPage kb={kb} onChanged={fetchKb} />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }} align="center">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/admin/kb")}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          <QuestionCircleOutlined /> {kb.name}
        </Title>
        <Tag color="green">文档型知识库</Tag>
        {kb.label && <Tag>{kb.label}</Tag>}
      </Space>
      {kb.description && (
        <Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
          {kb.description}
        </Text>
      )}

      <Tabs
        defaultActiveKey="qa"
        items={[
          {
            key: "qa",
            label: (
              <span>
                <QuestionCircleOutlined /> 问答集（{qaTotal}）
              </span>
            ),
            children: (
              <Card
                size="small"
                extra={
                  <Button type="primary" icon={<PlusOutlined />} size="small" onClick={openCreateQA}>
                    录入信息
                  </Button>
                }
              >
                <Table
                  columns={qaColumns}
                  dataSource={qaItems}
                  rowKey="id"
                  loading={qaLoading}
                  size="middle"
                  pagination={{
                    current: qaPage,
                    pageSize: 20,
                    total: qaTotal,
                    onChange: setQaPage,
                    showTotal: (t) => `共 ${t} 条问答`,
                    showSizeChanger: false,
                  }}
                />
              </Card>
            ),
          },
          {
            key: "docs",
            label: (
              <span>
                <FileTextOutlined /> 文档集（{docTotal}）
              </span>
            ),
            children: (
              <Space direction="vertical" size={12} style={{ width: "100%" }}>
                <Card size="small">
                  <Dragger
                    accept=".txt,.md,.pdf,.docx,.csv,.xlsx"
                    showUploadList={false}
                    beforeUpload={(file) => {
                      handleUpload(file);
                      return false;
                    }}
                    disabled={uploading}
                  >
                    <p className="ant-upload-drag-icon">
                      <InboxOutlined />
                    </p>
                    <p className="ant-upload-text">点击或拖拽文件到此处上传</p>
                    <p className="ant-upload-hint">支持 TXT、Markdown、PDF、Word、Excel、CSV，单文件最大 50MB</p>
                  </Dragger>
                </Card>
                <Card size="small" title="文档列表">
                  <Table
                    columns={docColumns}
                    dataSource={docs}
                    rowKey="id"
                    loading={docLoading}
                    size="middle"
                    pagination={{
                      current: docPage,
                      pageSize: 20,
                      total: docTotal,
                      onChange: setDocPage,
                      showTotal: (t) => `共 ${t} 个文档`,
                      showSizeChanger: false,
                    }}
                  />
                </Card>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingQa ? "编辑问答" : "录入信息"}
        open={qaModalOpen}
        onCancel={() => setQaModalOpen(false)}
        onOk={handleQaSubmit}
        confirmLoading={qaSaving}
        width={560}
      >
        <Form form={qaForm} layout="vertical" requiredMark={false} style={{ marginTop: 8 }}>
          <Form.Item
            name="question"
            label="问题"
            rules={[{ required: true, message: "请输入问题" }]}
          >
            <Input placeholder="如：查询今年阿坝州宗教方面的要闻" maxLength={500} />
          </Form.Item>
          <Form.Item
            name="answer"
            label="答案"
            rules={[{ required: true, message: "请输入答案" }]}
          >
            <TextArea placeholder="输入该问题的标准答案，用于提升会话效果" rows={5} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeBaseDetailPage;
