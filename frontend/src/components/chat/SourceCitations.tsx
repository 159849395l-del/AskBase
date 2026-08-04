/** 引用来源展示组件 — 可折叠的知识库片段卡片 */

import React from "react";
import { Card, Collapse, Tag, Typography, Space, theme } from "antd";
import { FileTextOutlined, PercentageOutlined } from "@ant-design/icons";
import type { SourceItem } from "../../types/chat";

const { Text, Paragraph } = Typography;

interface SourceCitationsProps {
  sources: SourceItem[];
}

const SourceCitations: React.FC<SourceCitationsProps> = ({ sources }) => {
  const { token: themeToken } = theme.useToken();

  if (!sources || sources.length === 0) return null;

  const items = sources.map((source, idx) => ({
    key: `${idx}`,
    label: (
      <Space size="small">
        <FileTextOutlined />
        <Text strong>来源{idx + 1}: </Text>
        <Text>{source.filename}</Text>
        <Tag color="blue" style={{ fontSize: 11 }}>
          <PercentageOutlined /> {(source.similarity_score * 100).toFixed(1)}%
        </Tag>
        {source.product_category && (
          <Tag color="green" style={{ fontSize: 11 }}>
            {source.product_category}
          </Tag>
        )}
      </Space>
    ),
    children: (
      <div
        style={{
          padding: "8px 12px",
          background: themeToken.colorFillAlter,
          borderRadius: 8,
          fontSize: 13,
          lineHeight: 1.6,
          color: themeToken.colorTextSecondary,
        }}
      >
        <Paragraph
          ellipsis={{ rows: 4, expandable: true, symbol: "展开全文" }}
          style={{ margin: 0 }}
        >
          {source.chunk_text}
        </Paragraph>
      </div>
    ),
  }));

  return (
    <div style={{ marginTop: 12 }}>
      <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: "block" }}>
        📚 引用来源 ({sources.length} 个相关片段)
      </Text>
      <Collapse
        size="small"
        items={items}
        ghost
        style={{ background: "transparent" }}
      />
    </div>
  );
};

export default SourceCitations;
