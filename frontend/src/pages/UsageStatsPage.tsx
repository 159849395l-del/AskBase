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
  Spin,
  Statistic,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs, { Dayjs } from "dayjs";

import { getUsageOverview } from "../api/usage";
import type { UsageOverview } from "../types/usage";

const { RangePicker } = DatePicker;
const { Text } = Typography;

/** 页面可见时的自动刷新间隔 */
const POLL_INTERVAL_MS = 30000;
/** 默认统计近 30 天 */
const DEFAULT_RANGE_DAYS = 30;

const UsageStatsPage: React.FC = () => {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(DEFAULT_RANGE_DAYS - 1, "day"),
    dayjs(),
  ]);
  const [overview, setOverview] = useState<UsageOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const load = useCallback(async (target: [Dayjs, Dayjs]) => {
    setLoading(true);
    try {
      const data = await getUsageOverview({
        start: target[0].format("YYYY-MM-DD"),
        end: target[1].format("YYYY-MM-DD"),
      });
      setOverview(data);
      setLoadFailed(false);
    } catch {
      setLoadFailed(true);
      message.error("用量数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  // 打开即拉取；切换时间范围后重新拉取
  useEffect(() => {
    load(range);
  }, [range, load]);

  // 页面可见时定时刷新；切到后台标签页不发请求，避免空转
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") {
        load(range);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [range, load]);

  const totals = overview?.totals;
  const estimatedCalls = overview?.excluded?.estimated_calls ?? 0;
  // 「没有消耗」和「没取到数据」必须分开：前者是空态，后者是错误态，
  // 否则首次加载或请求失败时，四张 0 卡片会被读成"零消耗"。
  const hasData = overview !== null;
  const isEmpty = hasData && totals!.llm_calls === 0 && totals!.total_tokens === 0;

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="用量统计"
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => load(range)}
            loading={loading}
          >
            刷新
          </Button>
        }
      >
        <RangePicker
          value={range}
          allowClear={false}
          onChange={(value) => {
            if (value && value[0] && value[1]) {
              setRange([value[0], value[1]]);
            }
          }}
          style={{ marginBottom: 16 }}
        />

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
                      groupSeparator=","
                    />
                  </Card>
                </Col>
                <Col xs={12} md={8}>
                  <Card size="small">
                    <Statistic
                      title="输入 Token"
                      value={totals?.prompt_tokens ?? 0}
                      groupSeparator=","
                    />
                  </Card>
                </Col>
                <Col xs={12} md={8}>
                  <Card size="small">
                    <Statistic
                      title="输出 Token"
                      value={totals?.completion_tokens ?? 0}
                      groupSeparator=","
                    />
                  </Card>
                </Col>
              </Row>
              )}
            </>
          )}
        </Spin>

        <Text type="secondary" style={{ display: "block", marginTop: 16, fontSize: 12 }}>
          仅统计模型服务返回真实用量的成功调用。「问答次数」按用户提问计，一次提问算一次；
          「模型调用次数」含查询改写、上下文压缩、Text-to-SQL、工具调用等内部编排产生的调用，
          因此通常大于问答次数。知识库索引与爬虫消耗不计入。
        </Text>
      </Card>
    </div>
  );
};

export default UsageStatsPage;
