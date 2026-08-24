/** 引用来源展示组件 — 可折叠的知识库片段卡片（支持 SQL 来源特殊展示） */

import React from "react";
import { Card, Collapse, Tag, Typography, Space, theme } from "antd";
import {
  FileTextOutlined,
  PercentageOutlined,
  CodeOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";
import type { SourceItem } from "../../types/chat";

const { Text, Paragraph } = Typography;

interface SourceCitationsProps {
  sources: SourceItem[];
}

const SourceCitations: React.FC<SourceCitationsProps> = ({ sources }) => {
  const { token: themeToken } = theme.useToken();

  if (!sources || sources.length === 0) return null;

  const items = sources.map((source, idx) => {
    const isSql = source.kind === "sql";
    const isDbResult = source.kind === "db_result";
    const label = (
      <Space size="small">
        {isSql ? (
          <CodeOutlined style={{ color: "#993556" }} />
        ) : isDbResult ? (
          <DatabaseOutlined style={{ color: "#534AB7" }} />
        ) : (
          <FileTextOutlined />
        )}
        <Text strong>来源{idx + 1}: </Text>
        <Text>{source.filename}</Text>
        {isSql ? (
          <Tag color="magenta" style={{ fontSize: 11 }}>
            生成查询
          </Tag>
        ) : isDbResult ? (
          <Tag color="purple" style={{ fontSize: 11 }}>
            查询结果
          </Tag>
        ) : source.score_type === "bm25" ? (
          <Tag color="orange" style={{ fontSize: 11 }}>
            关键词命中
          </Tag>
        ) : (
          <Tag color="blue" style={{ fontSize: 11 }}>
            <PercentageOutlined /> {(source.similarity_score * 100).toFixed(1)}%
          </Tag>
        )}
      </Space>
    );

    let content: React.ReactNode;
    if (isSql) {
      // SQL 来源：用代码块展示
      content = (
        <pre
          style={{
            margin: 0,
            padding: 10,
            background: themeToken.colorBgLayout,
            borderRadius: 8,
            fontSize: 12,
            lineHeight: 1.6,
            overflowX: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            color: themeToken.colorText,
          }}
        >
          {source.sql || source.chunk_text}
        </pre>
      );
    } else {
      content = (
        <Paragraph
          ellipsis={{ rows: 4, expandable: true, symbol: "展开全文" }}
          style={{ margin: 0 }}
        >
          {source.chunk_text}
        </Paragraph>
      );
    }

    return {
      key: `${idx}`,
      label,
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
          {content}
        </div>
      ),
    };
  });

  return (
    <div style={{ marginTop: 12 }}>
      <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: "block" }}>
        📚 最匹配的 {sources.length} 个来源
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
