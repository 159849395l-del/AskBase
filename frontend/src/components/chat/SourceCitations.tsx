/** 引用来源展示组件 — 可折叠的来源卡片（知识库片段 / SQL / 数据库结果 / 网页）
 *
 * 编号规则：正文里的 [来源N] 与这里的「来源N」是同一套 —— 编号 = 在列表中的位置。
 */

import React from "react";
import { Card, Collapse, Tag, Typography, Space, theme } from "antd";
import {
  FileTextOutlined,
  PercentageOutlined,
  CodeOutlined,
  DatabaseOutlined,
  LinkOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import type { SourceItem } from "../../types/chat";

const { Text, Paragraph } = Typography;

interface SourceCitationsProps {
  sources: SourceItem[];
}

/** 发布时间：后端给的是 ISO 串，只展示到日 */
function formatPublished(published?: string | null): string {
  if (!published) return "";
  const d = dayjs(published);
  return d.isValid() ? d.format("YYYY-MM-DD") : published;
}

const SourceCitations: React.FC<SourceCitationsProps> = ({ sources }) => {
  const { token: themeToken } = theme.useToken();

  if (!sources || sources.length === 0) return null;

  const items = sources.map((source, idx) => {
    const isSql = source.kind === "sql";
    const isDbResult = source.kind === "db_result";
    const isWeb = source.kind === "web";
    const label = (
      <Space size="small">
        {isSql ? (
          <CodeOutlined style={{ color: "#993556" }} />
        ) : isDbResult ? (
          <DatabaseOutlined style={{ color: "#534AB7" }} />
        ) : isWeb ? (
          <LinkOutlined style={{ color: "#0F766E" }} />
        ) : (
          <FileTextOutlined />
        )}
        <Text strong>来源{idx + 1}: </Text>
        {isWeb && source.url ? (
          // 标题本身就是链接：用户第一眼看到的是标题，不该为了点开还得去找下面的 URL
          <Typography.Link href={source.url} target="_blank" rel="noreferrer">
            {source.title || source.filename}
          </Typography.Link>
        ) : (
          <Text>{source.title || source.filename}</Text>
        )}
        {isSql ? (
          <Tag color="magenta" style={{ fontSize: 11 }}>
            生成查询
          </Tag>
        ) : isDbResult ? (
          <Tag color="purple" style={{ fontSize: 11 }}>
            查询结果
          </Tag>
        ) : isWeb ? (
          <Tag color="green" style={{ fontSize: 11 }}>
            网页
          </Tag>
        ) : source.score_type === "bm25" ? (
          <Tag color="orange" style={{ fontSize: 11 }}>
            关键词命中
          </Tag>
        ) : (
          <Tag color="blue" style={{ fontSize: 11 }}>
            <PercentageOutlined /> {((source.similarity_score ?? 0) * 100).toFixed(1)}%
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
    } else if (isWeb) {
      // 网页来源：链接必须可点，否则「来源」等于没有
      content = (
        <div>
          {source.url && (
            <Paragraph style={{ margin: 0, wordBreak: "break-all" }}>
              <Typography.Link href={source.url} target="_blank" rel="noreferrer">
                {source.url}
              </Typography.Link>
            </Paragraph>
          )}
          {source.published && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              发布时间：{formatPublished(source.published)}
            </Text>
          )}
          {source.snippet && (
            <Paragraph
              ellipsis={{ rows: 4, expandable: true, symbol: "展开全文" }}
              style={{ margin: 0, marginTop: 6 }}
            >
              {source.snippet}
            </Paragraph>
          )}
        </div>
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
      key: String(idx),
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
