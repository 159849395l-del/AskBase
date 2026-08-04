/** 消息气泡组件 — 支持 Markdown 渲染和引用来源展示 */

import React from "react";
import { Typography, Tag, theme } from "antd";
import { UserOutlined, RobotOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import type { MessageItem } from "../../types/chat";
import SourceCitations from "./SourceCitations";

const { Text } = Typography;

interface MessageBubbleProps {
  message: MessageItem;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const { token: themeToken } = theme.useToken();
  const isUser = message.role === "user";

  return (
    <div
      style={{
        display: "flex",
        flexDirection: isUser ? "row-reverse" : "row",
        gap: 12,
        marginBottom: 24,
        alignItems: "flex-start",
      }}
    >
      {/* 头像 */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: "50%",
          background: isUser ? themeToken.colorPrimary : themeToken.colorSuccess,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {isUser ? (
          <UserOutlined style={{ color: "#fff", fontSize: 18 }} />
        ) : (
          <RobotOutlined style={{ color: "#fff", fontSize: 18 }} />
        )}
      </div>

      {/* 消息内容 */}
      <div
        style={{
          maxWidth: "75%",
          padding: "12px 16px",
          borderRadius: 12,
          background: isUser ? themeToken.colorPrimaryBg : themeToken.colorBgContainer,
          border: `1px solid ${themeToken.colorBorderSecondary}`,
        }}
      >
        {isUser ? (
          <Text style={{ whiteSpace: "pre-wrap" }}>{message.content}</Text>
        ) : (
          <div className="markdown-body">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* 引用来源 */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCitations sources={message.sources} />
        )}

        {/* 时间戳 */}
        <div style={{ marginTop: 6, textAlign: "right" }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {message.created_at ? new Date(message.created_at).toLocaleTimeString("zh-CN") : ""}
          </Text>
          {message.token_count && (
            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
              {message.token_count} tokens
            </Text>
          )}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;
