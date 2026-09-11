/** 用量统计页面 — 仅管理员 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Row,
  Segmented,
  Spin,
  Statistic,
  Table,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { Column, Line } from "@ant-design/plots";
import dayjs, { Dayjs } from "dayjs";
import type { ColumnsType } from "antd/es/table";

import { getUsageOverview, getUsageTimeseries } from "../api/usage";
import type {
  UsageAgentRow,
  UsageGranularity,
  UsageOverview,
  UsageTimeseries,
} from "../types/usage";

const { RangePicker } = DatePicker;
const { Text } = Typography;

/** 页面可见时的自动刷新间隔 */
const POLL_INTERVAL_MS = 30000;
/** 明细表七列在窄屏下横向滚动的最小宽度 */
const AGENT_TABLE_SCROLL_X = 760;
/** 两张趋势图的高度 */
const CHART_HEIGHT = 260;
/**
 * 单次查询允许的最大时间桶数，与后端 usage_stats_service.MAX_BUCKETS 对应。
 * 这里只用来限制日期选择范围，真正的拒绝仍由后端负责。
 */
const MAX_BUCKETS = 400;

/** token 数字统一千分位：卡片与表格共用同一种格式化，避免两套规则 */
const formatTokens = (value: number | string) => Number(value).toLocaleString("zh-CN");

/** 明细表列定义（纯常量，不依赖组件状态） */
const AGENT_COLUMNS: ColumnsType<UsageAgentRow> = [
  { title: "智能体", dataIndex: "agent_name", key: "agent_name" },
  { title: "问答次数", dataIndex: "requests", key: "requests", align: "right" },
  { title: "模型调用次数", dataIndex: "llm_calls", key: "llm_calls", align: "right" },
  {
    title: "输入 Token",
    dataIndex: "prompt_tokens",
    key: "prompt_tokens",
    align: "right",
    render: formatTokens,
  },
  {
    title: "输出 Token",
    dataIndex: "completion_tokens",
    key: "completion_tokens",
    align: "right",
    render: formatTokens,
  },
  {
    title: "总 Token",
    dataIndex: "total_tokens",
    key: "total_tokens",
    align: "right",
    render: formatTokens,
  },
  {
    title: "最近调用",
    dataIndex: "last_called_at",
    key: "last_called_at",
    render: (value: string | null) =>
      value ? dayjs(value).format("YYYY-MM-DD HH:mm") : "—",
  },
];

const GRANULARITY_OPTIONS = [
  { label: "日", value: "day" },
  { label: "月", value: "month" },
  { label: "年", value: "year" },
];

/** 从接口错误里取出后端给的说明，用于把「跨度过大」这类原因如实告诉用户 */
const detailOf = (err: unknown): string | undefined => {
  const data = (err as { response?: { data?: { detail?: unknown } } })?.response?.data;
  return typeof data?.detail === "string" ? data.detail : undefined;
};

const UsageStatsPage: React.FC = () => {
  const [granularity, setGranularity] = useState<UsageGranularity>("day");
  /** 用户自选区间；为 null 表示用后端按粒度推导的缺省区间 */
  const [customRange, setCustomRange] = useState<[Dayjs, Dayjs] | null>(null);
  /** 实际生效的区间，来自接口返回，因此前后端不会各算一套 */
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [overview, setOverview] = useState<UsageOverview | null>(null);
  const [series, setSeries] = useState<UsageTimeseries | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(
    async (custom: [Dayjs, Dayjs] | null, gran: UsageGranularity) => {
      setLoading(true);
      try {
        const explicit = custom
          ? {
              start: custom[0].format("YYYY-MM-DD"),
              end: custom[1].format("YYYY-MM-DD"),
            }
          : {};
        // 汇总与时间序列必须落在同一区间，否则卡片与图表对不上。
        // 缺省区间交给后端按粒度推导，前端不再复刻那套规则。
        const [overviewData, seriesData] = await Promise.all([
          getUsageOverview({ granularity: gran, ...explicit }),
          getUsageTimeseries({ granularity: gran, ...explicit }),
        ]);
        setOverview(overviewData);
        setSeries(seriesData);
        setRange([dayjs(overviewData.start), dayjs(overviewData.end)]);
        setLoadFailed(false);
      } catch (err) {
        setLoadFailed(true);
        // 把后端的原因如实透出（例如「时间跨度过大…请改用更粗的粒度」）
        message.error(detailOf(err) ?? "用量数据加载失败");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // 打开即拉取；切换区间或粒度后重新拉取
  useEffect(() => {
    load(customRange, granularity);
  }, [customRange, granularity, load]);

  // 页面可见时定时刷新；切到后台标签页不发请求，避免空转
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") {
        load(customRange, granularity);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [customRange, granularity, load]);

  const handleGranularityChange = (value: string | number) => {
    setGranularity(value as UsageGranularity);
    // 切换粒度即回到该粒度的缺省区间，不需要记住上次的范围
    setCustomRange(null);
  };

  const disabledDate = (current: Dayjs) => {
    if (!current) return false;
    if (current.isAfter(dayjs(), "day")) return true; // 不选未来
    if (granularity === "day") {
      // 日粒度最多 MAX_BUCKETS 天，避免选出后端必然拒绝的区间
      return current.isBefore(dayjs().subtract(MAX_BUCKETS - 1, "day"), "day");
    }
    return false;
  };

  const totals = overview?.totals;
  const estimatedCalls = overview?.excluded?.estimated_calls ?? 0;
  // 「没有消耗」和「没取到数据」必须分开：前者是空态，后者是错误态，
  // 否则首次加载或请求失败时，几张 0 卡片会被读成"零消耗"。
  const hasData = overview !== null;
  const isEmpty = hasData && totals!.llm_calls === 0 && totals!.total_tokens === 0;

  const points = series?.points ?? [];
  // 折线要区分输入与输出：把一个时间桶摊成两条线
  const tokenTrend = points.flatMap((point) => [
    { bucket: point.bucket, kind: "输入 Token", tokens: point.prompt_tokens },
    { bucket: point.bucket, kind: "输出 Token", tokens: point.completion_tokens },
  ]);

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="用量统计"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => load(customRange, granularity)}
            loading={loading}
          >
            刷新
          </Button>
        }
      >
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <Segmented
            options={GRANULARITY_OPTIONS}
            value={granularity}
            onChange={handleGranularityChange}
          />
          <RangePicker
            value={range}
            allowClear={false}
            disabledDate={disabledDate}
            onChange={(value) => {
              if (value && value[0] && value[1]) {
                setCustomRange([value[0], value[1]]);
              }
            }}
          />
        </div>

        <Spin spinning={loading}>
          {!hasData ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                loadFailed ? "用量数据加载失败，请稍后重试" : "正在加载用量数据…"
              }
            />
          ) : (
            <>
              {/* 提示条必须在空态之上：整区间都是估算调用时，合计为 0 但并非「没人用」 */}
              {estimatedCalls > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                  message={`本区间另有 ${estimatedCalls} 次调用未返回用量，未计入统计`}
                  description="这些调用按字符估算不出可信的 token 数，因此既不计数也不计消耗。若该数字持续增长，说明模型端点没有返回用量。"
                />
              )}
              {isEmpty ? (
                <Empty description="暂无用量数据 — 统计自本次升级后开始记录，历史问答不会回溯计入" />
              ) : (
                <>
                  <Row gutter={[16, 16]}>
                    <Col xs={12} md={8}>
                      <Card size="small">
                        <Statistic title="问答次数" value={totals?.requests ?? 0} />
                      </Card>
                    </Col>
                    <Col xs={12} md={8}>
                      <Card size="small">
                        <Statistic title="模型调用次数" value={totals?.llm_calls ?? 0} />
                      </Card>
                    </Col>
                    <Col xs={12} md={8}>
                      <Card size="small">
                        <Statistic
                          title="总 Token"
                          value={totals?.total_tokens ?? 0}
                          formatter={formatTokens}
                        />
                      </Card>
                    </Col>
                    <Col xs={12} md={8}>
                      <Card size="small">
                        <Statistic
                          title="输入 Token"
                          value={totals?.prompt_tokens ?? 0}
                          formatter={formatTokens}
                        />
                      </Card>
                    </Col>
                    <Col xs={12} md={8}>
                      <Card size="small">
                        <Statistic
                          title="输出 Token"
                          value={totals?.completion_tokens ?? 0}
                          formatter={formatTokens}
                        />
                      </Card>
                    </Col>
                  </Row>

                  <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
                    <Col xs={24} xl={12}>
                      <Card size="small" title="Token 变化趋势">
                        <Line
                          data={tokenTrend}
                          xField="bucket"
                          yField="tokens"
                          colorField="kind"
                          height={CHART_HEIGHT}
                        />
                      </Card>
                    </Col>
                    <Col xs={24} xl={12}>
                      <Card size="small" title="调用次数变化">
                        <Column
                          data={points}
                          xField="bucket"
                          yField="llm_calls"
                          height={CHART_HEIGHT}
                        />
                      </Card>
                    </Col>
                  </Row>

                  <Table<UsageAgentRow>
                    rowKey={(row) => (row.agent_id === null ? "unbound" : String(row.agent_id))}
                    style={{ marginTop: 16 }}
                    size="small"
                    dataSource={overview?.agents ?? []}
                    pagination={false}
                    scroll={{ x: AGENT_TABLE_SCROLL_X }}
                    columns={AGENT_COLUMNS}
                  />
                </>
              )}
            </>
          )}
        </Spin>

        <Text type="secondary" style={{ display: "block", marginTop: 16, fontSize: 12 }}>
          仅统计模型服务返回真实用量的成功调用。「问答次数」按用户提问计，一次提问算一次；
          「模型调用次数」含查询改写、上下文压缩、Text-to-SQL、工具调用等内部编排产生的调用，
          因此通常大于问答次数。没有数据的时间桶按 0 计，曲线保持连续。
          知识库索引与爬虫消耗不计入。
        </Text>
      </Card>
    </div>
  );
};

export default UsageStatsPage;
