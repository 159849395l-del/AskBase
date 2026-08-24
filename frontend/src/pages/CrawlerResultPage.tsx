/** 爬虫提取结果详情页 */

import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Descriptions, Button, Spin, Alert, Typography,
  Space, Tag, Divider, Table,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { getResultDetail } from "../api/crawler";
import type { CrawlResult } from "../types/crawler";
import { RESULT_STATUS_LABELS } from "../types/crawler";

const { Title, Text, Paragraph } = Typography;

const CrawlerResultPage: React.FC = () => {
  const { taskId, resultId } = useParams<{ taskId: string; resultId: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<CrawlResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const r = await getResultDetail(Number(taskId), Number(resultId));
        setResult(r);
      } catch {
        // handled below
      }
      setLoading(false);
    };
    fetchResult();
  }, [taskId, resultId]);

  if (loading) {
    return (
      <div style={{ padding: 24, textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!result) {
    return (
      <div style={{ padding: 24 }}>
        <Alert message="结果不存在" type="error" showIcon />
        <Button style={{ marginTop: 16 }} onClick={() => navigate(`/admin/crawler/tasks/${taskId}`)}>
          返回任务详情
        </Button>
      </div>
    );
  }

  // 提取的数据字段
  const dataFields = result.data
    ? Object.entries(result.data).map(([key, value]) => ({
        key,
        value: typeof value === "object" ? JSON.stringify(value, null, 2) : String(value),
      }))
    : [];

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(`/admin/crawler/tasks/${taskId}`)}
        >
          返回任务详情
        </Button>
      </Space>

      <Title level={4}>提取结果详情</Title>

      {/* 基本信息 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="结果ID">{result.id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={result.status === "VALID" ? "success" : "default"}>
              {RESULT_STATUS_LABELS[result.status] || result.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="URL" span={2}>
            <Text copyable style={{ wordBreak: "break-all" }}>
              {result.url}
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="源URL">
            {result.sourceUrl || "-"}
          </Descriptions.Item>
          <Descriptions.Item label="提取时间">
            {result.extractedAt ? new Date(result.extractedAt).toLocaleString("zh-CN") : "-"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 提取的数据 */}
      <Card size="small" title="提取数据" style={{ marginBottom: 16 }}>
        {dataFields.length > 0 ? (
          <Table
            dataSource={dataFields}
            columns={[
              { title: "字段", dataIndex: "key", key: "key", width: 200 },
              {
                title: "值",
                dataIndex: "value",
                key: "value",
                render: (v: string) => (
                  <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 12, maxHeight: 300, overflow: "auto" }}>
                    {v}
                  </pre>
                ),
              },
            ]}
            rowKey="key"
            pagination={false}
            size="small"
          />
        ) : (
          <Text type="secondary">暂无提取数据</Text>
        )}
      </Card>

      {/* 页面文本预览 */}
      {result.pageText && (
        <Card size="small" title="页面文本预览（前 5000 字符）">
          <pre
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              fontSize: 12,
              maxHeight: 400,
              overflow: "auto",
              background: "#f5f5f5",
              padding: 12,
              borderRadius: 4,
            }}
          >
            {result.pageText}
          </pre>
        </Card>
      )}
    </div>
  );
};

export default CrawlerResultPage;
