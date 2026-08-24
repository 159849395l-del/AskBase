/** 爬虫任务列表页 */

import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card, Table, Button, Space, Tag, Input, Select, message,
  Popconfirm, Typography, theme,
} from "antd";
import {
  PlusOutlined, SearchOutlined, ReloadOutlined,
  DeleteOutlined, PlayCircleOutlined, EyeOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { CrawlTask, TaskStatusEnum } from "../types/crawler";
import { TASK_STATUS_LABELS, TASK_STATUS_COLORS } from "../types/crawler";
import { listTasks, deleteTask, submitTask } from "../api/crawler";

const { Title } = Typography;

const CrawlerTaskListPage: React.FC = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<CrawlTask[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [keyword, setKeyword] = useState("");
  const [searchText, setSearchText] = useState("");
  const { token: themeToken } = theme.useToken();

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await listTasks(page, 20, statusFilter, searchText || undefined);
      setTasks(resp.items);
      setTotal(resp.total);
    } catch {
      message.error("获取任务列表失败");
    }
    setLoading(false);
  }, [page, statusFilter, searchText]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleDelete = async (id: number) => {
    try {
      await deleteTask(id);
      message.success("任务已删除");
      fetchTasks();
    } catch {
      message.error("删除失败");
    }
  };

  const handleSubmit = async (id: number) => {
    try {
      const resp = await submitTask(id);
      message.success(resp.message);
      fetchTasks();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "提交失败");
    }
  };

  const handleSearch = () => {
    setSearchText(keyword);
    setPage(0);
  };

  const columns: ColumnsType<CrawlTask> = [
    {
      title: "任务编号",
      dataIndex: "taskNo",
      key: "taskNo",
      width: 150,
    },
    {
      title: "标题",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (text: string, record: CrawlTask) => (
        <a onClick={() => navigate(`/admin/crawler/tasks/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: "种子URL数",
      dataIndex: "seedUrls",
      key: "seedUrls",
      width: 100,
      render: (urls: string[]) => urls?.length || 0,
    },
    {
      title: "最大页数",
      dataIndex: "maxPages",
      key: "maxPages",
      width: 80,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: TaskStatusEnum) => (
        <Tag color={TASK_STATUS_COLORS[s] || "default"}>
          {TASK_STATUS_LABELS[s] || s}
        </Tag>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "createdAt",
      key: "createdAt",
      width: 220,
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 220,
      render: (_, record) => (
        <Space wrap>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/admin/crawler/tasks/${record.id}`)}
          >
            详情
          </Button>
          {record.status === "PENDING" && (
            <Button
              type="link"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => handleSubmit(record.id)}
            >
              启动
            </Button>
          )}
          <Popconfirm title="确定删除此任务？所有相关数据将被移除" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginBottom: 16 }}>
        爬虫任务管理
      </Title>

      {/* 工具栏 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input
            placeholder="搜索标题/描述"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 240 }}
            allowClear
          />
          <Select
            allowClear
            placeholder="筛选状态"
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPage(0);
            }}
            style={{ width: 120 }}
            options={[
              { label: "全部", value: "" },
              { label: "待处理", value: "PENDING" },
              { label: "运行中", value: "RUNNING" },
              { label: "已完成", value: "COMPLETED" },
              { label: "部分完成", value: "PARTIAL" },
              { label: "失败", value: "FAILED" },
              { label: "已取消", value: "CANCELLED" },
            ]}
          />
          <Button icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate("/admin/crawler/tasks/new")}
          >
            新建任务
          </Button>
        </Space>
      </Card>

      {/* 任务列表 */}
      <Table
        columns={columns}
        dataSource={tasks}
        rowKey="id"
        loading={loading}
        size="middle"
        pagination={{
          current: page + 1,
          pageSize: 20,
          total,
          onChange: (p) => setPage(p - 1),
          showTotal: (t) => `共 ${t} 个任务`,
          showSizeChanger: false,
        }}
      />
    </div>
  );
};

export default CrawlerTaskListPage;
