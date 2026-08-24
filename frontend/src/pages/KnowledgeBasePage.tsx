/** 知识库管理页面 — 仅管理员可访问 */

import React, { useEffect, useState, useCallback } from "react";
import {
  Card,
  Table,
  Button,
  Upload,
  Space,
  Tag,
  Statistic,
  Row,
  Col,
  message,
  Modal,
  Popconfirm,
  Select,
  theme,
  Typography,
} from "antd";
import {
  UploadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  CloudSyncOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { DocumentItem, KBStatsResponse } from "../types/kb";
import {
  listDocuments,
  uploadDocument,
  deleteDocument,
  getKBStats,
  reindexKB,
  ingestCrawlData,
} from "../api/kb";

const { Dragger } = Upload;
const { Title } = Typography;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  processing: { color: "processing", label: "处理中" },
  indexed: { color: "success", label: "已索引" },
  failed: { color: "error", label: "失败" },
};

const KnowledgeBasePage: React.FC = () => {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<KBStatsResponse | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [uploading, setUploading] = useState(false);
  const [syncingCrawl, setSyncingCrawl] = useState(false);
  const { token: themeToken } = theme.useToken();

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await listDocuments(page, 20, statusFilter);
      setDocs(resp.items);
      setTotal(resp.total);
    } catch {
      message.error("获取文档列表失败");
    }
    setLoading(false);
  }, [page, statusFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const s = await getKBStats();
      setStats(s);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchDocs();
    fetchStats();
  }, [fetchDocs, fetchStats]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      await uploadDocument(file);
      message.success(`文档 "${file.name}" 上传成功，正在后台向量化...`);
      fetchDocs();
      fetchStats();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "上传失败");
    }
    setUploading(false);
    return false; // 阻止默认上传行为
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteDocument(id);
      message.success("文档已删除");
      fetchDocs();
      fetchStats();
    } catch {
      message.error("删除失败");
    }
  };

  const handleReindex = async () => {
    try {
      const resp = await reindexKB();
      message.success(resp.message);
      fetchDocs();
      fetchStats();
    } catch {
      message.error("重建索引失败");
    }
  };

  // 同步 ai_crawl 爬虫数据到知识库（读 MySQL → 切分 → 摄入，幂等增量）
  const handleIngestCrawl = async () => {
    setSyncingCrawl(true);
    try {
      const resp = await ingestCrawlData();
      message.success("爬虫数据同步完成");
      // 展示摄入摘要（多行）
      if (resp.message && resp.message.includes("\n")) {
        Modal.info({
          title: "同步结果",
          width: 560,
          content: (
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, maxHeight: 360, overflow: "auto" }}>
              {resp.message}
            </pre>
          ),
        });
      }
      fetchDocs();
      fetchStats();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "同步失败，请确认 ai_crawl 的 MySQL 是否可访问");
    }
    setSyncingCrawl(false);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const columns: ColumnsType<DocumentItem> = [
    {
      title: "文件名",
      dataIndex: "filename",
      key: "filename",
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
    {
      title: "类型",
      dataIndex: "file_type",
      key: "file_type",
      width: 80,
      render: (t: string) => <Tag>{t.toUpperCase()}</Tag>,
    },
    {
      title: "大小",
      dataIndex: "file_size",
      key: "file_size",
      width: 100,
      render: (s: number) => formatFileSize(s),
    },
    {
      title: "块数",
      dataIndex: "chunk_count",
      key: "chunk_count",
      width: 80,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: string) => {
        const cfg = STATUS_MAP[s] || { color: "default", label: s };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: "上传时间",
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 80,
      render: (_, record) => (
        <Popconfirm title="确定删除此文档？所有相关向量数据将被移除" onConfirm={() => handleDelete(record.id)}>
          <Button type="text" danger icon={<DeleteOutlined />} size="small" />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginBottom: 16 }}>
        <DatabaseOutlined /> 知识库管理
      </Title>

      {/* 统计卡片 */}
      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card size="small">
              <Statistic title="文档总数" value={stats.total_documents} prefix={<FileTextOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic title="文本块总数" value={stats.total_chunks} prefix={<DatabaseOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="已索引"
                value={stats.by_status?.indexed || 0}
                valueStyle={{ color: themeToken.colorSuccess }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card size="small">
              <Statistic
                title="总大小"
                value={formatFileSize(stats.total_size_bytes)}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 上传区域 */}
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        title="上传文档"
        extra={
          <Space>
            <Button
              icon={<CloudSyncOutlined />}
              onClick={handleIngestCrawl}
              loading={syncingCrawl}
              size="small"
              type="primary"
              ghost
            >
              {syncingCrawl ? "同步中..." : "同步爬虫数据"}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleReindex} size="small">
              重建全量索引
            </Button>
          </Space>
        }
      >
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
          <p className="ant-upload-hint">
            支持 TXT、Markdown、PDF、Word、Excel、CSV 格式，单文件最大 50MB
          </p>
        </Dragger>
      </Card>

      {/* 文档列表 */}
      <Card
        size="small"
        title="文档列表"
        extra={
          <Space>
            <Select
              allowClear
              placeholder="筛选状态"
              value={statusFilter}
              onChange={(v) => {
                setStatusFilter(v);
                setPage(1);
              }}
              style={{ width: 120 }}
              size="small"
              options={[
                { label: "全部", value: "" },
                { label: "已索引", value: "indexed" },
                { label: "处理中", value: "processing" },
                { label: "失败", value: "failed" },
              ]}
            />
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={docs}
          rowKey="id"
          loading={loading}
          size="middle"
          pagination={{
            current: page,
            pageSize: 20,
            total,
            onChange: setPage,
            showTotal: (t) => `共 ${t} 个文档`,
            showSizeChanger: false,
          }}
        />
      </Card>
    </div>
  );
};

export default KnowledgeBasePage;
