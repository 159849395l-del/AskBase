/** 工具调用留痕 — 折叠展示本次回答调用了哪些工具、拿到了什么结果 */

import React from "react";
import { Collapse, Space, Typography, theme } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import type { ToolCallItem } from "../../types/chat";

const { Text, Paragraph } = Typography;

interface ToolCallsPanelProps {
  toolCalls: ToolCallItem[];
}

const ToolCallsPanel: React.FC<ToolCallsPanelProps> = ({ toolCalls }) => {
  const { token: themeToken } = theme.useToken();

  if (!toolCalls || toolCalls.length === 0) return null;

  const items = toolCalls.map((tool, idx) => ({
    key: String(idx),
    label: (
      <Space size="small">
        <ToolOutlined style={{ color: "#0F766E" }} />
        <Text strong>{tool.name}</Text>
      </Space>
    ),
    children: (
      <div
        style={{
          padding: "8px 12px",
          background: themeToken.colorFillAlter,
          borderRadius: 8,
          fontSize: 12,
          lineHeight: 1.6,
          color: themeToken.colorTextSecondary,
        }}
      >
        <Paragraph
          ellipsis={{ rows: 6, expandable: true, symbol: "展开全文" }}
          style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          {tool.content || "（无结果摘要）"}
        </Paragraph>
      </div>
    ),
  }));

  return (
    <div style={{ marginTop: 12 }}>
      <Text type="secondary" style={{ fontSize: 12, marginBottom: 4, display: "block" }}>
        🔧 调用了 {toolCalls.length} 个工具
      </Text>
      <Collapse size="small" items={items} ghost style={{ background: "transparent" }} />
    </div>
  );
};

export default ToolCallsPanel;
