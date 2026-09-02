/** 爬虫任务详情页 — SSE 实时进度 + 结果列表 + 定时配置 */

import React, { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Descriptions, Tag, Button, Space, Table, message,
  Typography, Spin, Alert, Divider, Modal, InputNumber, TimePicker,
  Switch, Form, Tabs, Statistic, Row, Col, Progress, Tooltip, Empty,
} from "antd";
import {
  ArrowLeftOutlined, PlayCircleOutlined, PauseCircleOutlined,
  ReloadOutlined, DownloadOutlined, BarChartOutlined,
  CheckCircleOutlined, CloseCircleOutlined, SyncOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import type {
  CrawlTask, CrawlResult, TaskStatusEnum, CrawlSchedule,
} from "../types/crawler";
import { TASK_STATUS_LABELS, TASK_STATUS_COLORS, RESULT_STATUS_LABELS } from "../types/crawler";
import {
  getTask, submitTask, restartTask, stopTask,
  listResults, exportResults, connectTaskSSE,
  getSchedule, saveSchedule, deleteSchedule,
} from "../api/crawler";

const { Title, Text } = Typography;

const CrawlerTaskDetailPage: React.FC = () => {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const id = Number(taskId);

  const [task, setTask] = useState<CrawlTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<CrawlResult[]>([]);
  const [resultsTotal, setResultsTotal] = useState(0);
  const [resultsPage, setResultsPage] = useState(0);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [schedule, setSchedule] = useState<CrawlSchedule | null>(null);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [scheduleForm] = Form.useForm();

  // SSE 实时状态
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [sseConnected, setSseConnected] = useState(false);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const esRef = useRef<EventSource | null>(null);

  // 定时器：非 SSE 时轮询
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTask = useCallback(async () => {
    try {
      const t = await getTask(id);
      setTask(t);
      setLiveStatus(t.status);
    } catch {
      message.error("获取任务详情失败");
    }
    setLoading(false);
  }, [id]);

  const fetchResults = useCallback(async () => {
    setResultsLoading(true);
    try {
      const resp = await listResults(id, resultsPage, 20);
      setResults(resp.items);
      setResultsTotal(resp.total);
    } catch {
      // ignore
    }
    setResultsLoading(false);
  }, [id, resultsPage]);

  const fetchSchedule = useCallback(async () => {
    try {
      const s = await getSchedule(id);
      setSchedule(s);
    } catch {
      // ignore
    }
  }, [id]);

  useEffect(() => {
    fetchTask();
    fetchResults();
    fetchSchedule();
  }, [fetchTask, fetchResults, fetchSchedule]);

  // SSE 连接
  useEffect(() => {
    if (!id) return;

    const es = connectTaskSSE(
      id,
      (event, data) => {
        setSseConnected(true);
        switch (event) {
          case "TASK_STATUS":
            setLiveStatus(data.status);
            setTask((prev) => prev ? { ...prev, status: data.status } : prev);
            addLog(`状态变更: ${data.status}`);
            break;
          case "TASK_ERROR":
            addLog(`错误: ${data.error}`);
            break;
          case "AGENT_LOG":
            addLog(`[${data.agent}] ${data.stage} - ${data.status}`);
            break;
          case "URL_PROGRESS":
            addLog(`[${data.crawlMode || "?"}] ${data.status}: ${data.url?.slice(0, 80)}`);
            break;
          case "STAGE_PROGRESS":
            addLog(`阶段 ${data.stage}: ${data.current}/${data.total}`);
            break;
          case "RESULT_NEW":
            addLog(`新结果: #${data.resultId}`);
            fetchResults();
            break;
        }
      },
      () => {
        setSseConnected(false);
      }
    );
    esRef.current = es;

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [id]);

  // 非 SSE 时轮询（任务运行时）
  useEffect(() => {
    if (sseConnected || !task) return;
    const isRunning = task.status !== "PENDING" && !["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"].includes(task.status);
    if (isRunning && !pollTimerRef.current) {
      pollTimerRef.current = setInterval(() => {
        fetchTask();
        fetchResults();
      }, 5000);
    }
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [sseConnected, task?.status, fetchTask, fetchResults]);

  const addLog = (msg: string) => {
    setProgressLog((prev) => {
      const next = [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`];
      return next.slice(-200);
    });
  };

  const handleSubmit = async () => {
    try {
      const resp = await submitTask(id);
      message.success(resp.message);
      fetchTask();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "提交失败");
    }
  };

  const handleRestart = async () => {
    try {
      await restartTask(id);
      message.success("任务已重置并重新提交");
      setProgressLog([]);
      fetchTask();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "重启失败");
    }
  };

  const handleStop = async () => {
    try {
      await stopTask(id);
      message.success("任务已停止");
      fetchTask();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "停止失败");
    }
  };

  const handleExport = async (format: "csv" | "json") => {
    try {
      const blob = await exportResults(id, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `task-${id}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch {
      message.error("导出失败");
    }
  };

  const handleSaveSchedule = async (values: any) => {
    try {
      const s = await saveSchedule(id, {
        // 后端 ScheduleRequest 用下划线命名（interval_days/run_time），
        // 传驼峰会被 Pydantic 当多余字段忽略，间隔天数会静默退回默认值 1
        interval_days: values.intervalDays,
        run_time: values.runTime ? values.runTime.format("HH:mm:ss") : "02:00:00",
        enabled: values.enabled ?? true,
      });
      setSchedule(s);
      setScheduleModalOpen(false);
      message.success("定时配置已保存");
    } catch (err: any) {
      message.error(err.response?.data?.detail || "保存失败");
    }
  };

  const handleDeleteSchedule = async () => {
    try {
      await deleteSchedule(id);
      setSchedule(null);
      setScheduleModalOpen(false);
      message.success("已取消定时爬取");
    } catch {
      message.error("删除失败");
    }
  };

  const isTerminal = task && ["COMPLETED", "PARTIAL", "FAILED", "CANCELLED"].includes(task.status);
  const isRunning = task && !isTerminal && task.status !== "PENDING";

  const resultColumns: ColumnsType<CrawlResult> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 60,
    },
    {
      title: "URL",
      dataIndex: "url",
      key: "url",
      ellipsis: true,
      render: (url: string) => (
        <Tooltip title={url}>
          <Text copyable={{ text: url }} style={{ fontSize: 12 }}>
            {url?.length > 60 ? url.slice(0, 60) + "..." : url}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (s: string) => (
        <Tag color={s === "VALID" ? "success" : "default"}>
          {RESULT_STATUS_LABELS[s] || s}
        </Tag>
      ),
    },
    {
      title: "提取时间",
      dataIndex: "extractedAt",
      key: "extractedAt",
      width: 150,
      render: (t: string | null) => t ? new Date(t).toLocaleString("zh-CN") : "-",
    },
  ];

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!task) {
    return (
      <div style={{ padding: 24 }}>
        <Alert message="任务不存在" type="error" showIcon />
        <Button style={{ marginTop: 16 }} onClick={() => navigate("/admin/crawler/tasks")}>
          返回列表
        </Button>
      </div>
    );
  }

  const statusColor = TASK_STATUS_COLORS[task.status as TaskStatusEnum] || "default";
  const statusLabel = TASK_STATUS_LABELS[task.status as TaskStatusEnum] || task.status;

  return (
    <div style={{ padding: 24 }}>
      {/* 顶部导航 */}
      <Space style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/admin/crawler/tasks")}
        >
          返回列表
        </Button>
      </Space>

      {/* 任务基本信息 */}
      <Card
        title={
          <Space>
            <span>{task.title}</span>
            <Tag color={statusColor}>{statusLabel}</Tag>
            {sseConnected && <Tag color="blue">实时</Tag>}
          </Space>
        }
        extra={
          <Space>
            {task.status === "PENDING" && (
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleSubmit}>
                启动任务
              </Button>
            )}
            {(isRunning || task.status === "PENDING") && (
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRestart}
                disabled={task.status === "PENDING"}
              >
                重启
              </Button>
            )}
            {isRunning && (
              <Button danger icon={<PauseCircleOutlined />} onClick={handleStop}>
                停止
              </Button>
            )}
            {isTerminal && (
              <Button
                type="primary"
                icon={<SyncOutlined />}
                onClick={handleRestart}
              >
                重新运行
              </Button>
            )}
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        <Descriptions column={2} size="small">
          <Descriptions.Item label="任务编号">{task.taskNo}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColor}>{statusLabel}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="种子URL数">{task.seedUrls?.length || 0}</Descriptions.Item>
          <Descriptions.Item label="最大页数">{task.maxPages}</Descriptions.Item>
          <Descriptions.Item label="最大深度">{task.maxDepth}</Descriptions.Item>
          <Descriptions.Item label="仅同域名">{task.sameDomainOnly ? "是" : "否"}</Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {task.description}
          </Descriptions.Item>
          {task.errorMessage && (
            <Descriptions.Item label="错误信息" span={2}>
              <Text type="danger">{task.errorMessage}</Text>
            </Descriptions.Item>
          )}
          <Descriptions.Item label="创建时间">
            {new Date(task.createdAt).toLocaleString("zh-CN")}
          </Descriptions.Item>
          <Descriptions.Item label="最后更新">
            {new Date(task.updatedAt).toLocaleString("zh-CN")}
          </Descriptions.Item>
          {task.startedAt && (
            <Descriptions.Item label="开始时间">
              {new Date(task.startedAt).toLocaleString("zh-CN")}
            </Descriptions.Item>
          )}
          {task.finishedAt && (
            <Descriptions.Item label="完成时间">
              {new Date(task.finishedAt).toLocaleString("zh-CN")}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      {/* 统计 + 进度 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="结果总数"
              value={resultsTotal}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="状态"
              value={statusLabel}
              valueStyle={{ color: isTerminal ? (task.status === "FAILED" ? "#ff4d4f" : "#52c41a") : "#1677ff" }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="爬取进度">
            <Progress
              percent={(() => {
                if (!task.stats) return 0;
                const s = task.stats;
                const max = Math.max(s.maxPages || task.maxPages || 1, 1);
                const done = (s.valid || 0) + (s.invalid || 0) + (s.failed || 0);
                if (task.status === "COMPLETED" || task.status === "PARTIAL") return 100;
                const total = Math.max(s.discovered || s.crawled || max, 1);
                return Math.min(Math.round((done / total) * 100), 100);
              })()}
              status={task.status === "FAILED" ? "exception" : (task.status === "COMPLETED" || task.status === "PARTIAL" ? "success" : "active")}
              format={(pct) => `${pct || 0}%`}
            />
          </Card>
        </Col>
      </Row>

      {/* 选项卡：结果列表 / 实时日志 / 定时配置 */}
      <Card size="small">
        <Tabs
          defaultActiveKey="results"
          style={{ minHeight: 400 }}
          items={[
            {
              key: "results",
              label: `提取结果 (${resultsTotal})`,
              children: (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <Space>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={() => handleExport("csv")}
                        size="small"
                        disabled={resultsTotal === 0}
                      >
                        导出 CSV
                      </Button>
                      <Button
                        icon={<DownloadOutlined />}
                        onClick={() => handleExport("json")}
                        size="small"
                        disabled={resultsTotal === 0}
                      >
                        导出 JSON
                      </Button>
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={fetchResults}
                        size="small"
                      >
                        刷新
                      </Button>
                    </Space>
                  </div>
                  <Table
                    columns={resultColumns}
                    dataSource={results}
                    rowKey="id"
                    loading={resultsLoading}
                    size="small"
                    pagination={{
                      current: resultsPage + 1,
                      pageSize: 20,
                      total: resultsTotal,
                      onChange: (p) => setResultsPage(p - 1),
                      showSizeChanger: false,
                      showTotal: (t) => `共 ${t} 条`,
                    }}
                    onRow={(record) => ({
                      onClick: () => navigate(`/admin/crawler/tasks/${id}/results/${record.id}`),
                      style: { cursor: "pointer" },
                    })}
                  />
                </>
              ),
            },
            {
              key: "logs",
              label: `实时日志 ${sseConnected ? "●" : "○"}`,
              children: (
                <div
                  style={{
                    background: "#1e1e1e",
                    color: "#d4d4d4",
                    padding: 12,
                    borderRadius: 4,
                    maxHeight: 400,
                    overflow: "auto",
                    fontFamily: "monospace",
                    fontSize: 12,
                  }}
                >
                  {progressLog.length === 0 ? (
                    <Empty description="暂无日志" />
                  ) : (
                    progressLog.map((log, i) => (
                      <div key={i}>{log}</div>
                    ))
                  )}
                </div>
              ),
            },
            {
              key: "schedule",
              label: "定时配置",
              children: (
                <div>
                  <Descriptions column={1} size="small">
                    <Descriptions.Item label="定时爬取">
                      {schedule ? (schedule.enabled ? "已启用" : "已禁用") : "未配置"}
                    </Descriptions.Item>
                    {schedule && (
                      <>
                        <Descriptions.Item label="间隔天数">
                          {schedule.intervalDays} 天
                        </Descriptions.Item>
                        <Descriptions.Item label="运行时间">
                          {schedule.runTime}
                        </Descriptions.Item>
                        <Descriptions.Item label="上次运行">
                          {schedule.lastRunAt ? new Date(schedule.lastRunAt).toLocaleString("zh-CN") : "从未运行"}
                        </Descriptions.Item>
                        <Descriptions.Item label="上次状态">
                          {schedule.lastStatus}
                        </Descriptions.Item>
                      </>
                    )}
                  </Descriptions>
                  <Space style={{ marginTop: 12 }}>
                    <Button
                      size="small"
                      onClick={() => {
                        scheduleForm.setFieldsValue({
                          intervalDays: schedule?.intervalDays || 1,
                          runTime: schedule?.runTime ? dayjs(schedule.runTime, "HH:mm:ss") : dayjs("02:00:00", "HH:mm:ss"),
                          enabled: schedule?.enabled ?? true,
                        });
                        setScheduleModalOpen(true);
                      }}
                    >
                      {schedule ? "编辑定时" : "配置定时"}
                    </Button>
                    {schedule && (
                      <Button size="small" danger onClick={handleDeleteSchedule}>
                        取消定时
                      </Button>
                    )}
                  </Space>
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* 定时配置 Modal */}
      <Modal
        title="定时爬取配置"
        open={scheduleModalOpen}
        onCancel={() => setScheduleModalOpen(false)}
        onOk={() => scheduleForm.submit()}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={scheduleForm}
          layout="vertical"
          onFinish={handleSaveSchedule}
          initialValues={{
            intervalDays: 1,
            runTime: dayjs("02:00:00", "HH:mm:ss"),
            enabled: true,
          }}
        >
          <Form.Item
            name="intervalDays"
            label="间隔天数"
            rules={[{ required: true, message: "请输入间隔天数" }]}
          >
            <InputNumber min={1} max={30} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item
            name="runTime"
            label="运行时间"
            rules={[{ required: true, message: "请选择运行时间" }]}
          >
            <TimePicker format="HH:mm:ss" />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CrawlerTaskDetailPage;
