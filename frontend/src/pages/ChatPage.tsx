/** 聊天主页面 */

import React, { useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Typography, Empty, theme } from "antd";
import { MessageOutlined } from "@ant-design/icons";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";

const { Title, Text } = Typography;

const ChatPage: React.FC = () => {
  const { convId } = useParams<{ convId?: string }>();
  const navigate = useNavigate();
  const messages = useChatStore((s) => s.messages);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stopStreaming = useChatStore((s) => s.stopStreaming);
  const user = useAuthStore((s) => s.user);
  const { token: themeToken } = theme.useToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (convId) {
      const id = parseInt(convId, 10);
      if (!isNaN(id) && id !== activeConversationId) {
        setActiveConversation(id);
      }
    }
  }, [convId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = async (content: string) => {
    if (!activeConversationId) {
      // 新建会话
      const { createNewConversation, setActiveConversation } = useChatStore.getState();
      const newId = await createNewConversation();
      await setActiveConversation(newId);
      navigate(`/chat/${newId}`, { replace: true });
      // 延迟一下等待状态更新
      setTimeout(() => {
        useChatStore.getState().sendMessage(content);
      }, 100);
    } else {
      await sendMessage(content);
    }
  };

  if (!activeConversationId && !convId) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Empty
          image={<MessageOutlined style={{ fontSize: 64, color: themeToken.colorPrimary }} />}
          description={
            <div>
              <Title level={4}>欢迎使用电商知识库问答系统</Title>
              <Text type="secondary">
                请在左侧选择会话或创建新会话开始提问
              </Text>
            </div>
          }
        >
          <div style={{ marginTop: 16 }}>
            <Text type="secondary" style={{ fontSize: 13 }}>
              提示：您可以询问任何关于电商商品的问题，例如：
            </Text>
            <div style={{ marginTop: 8 }}>
              {[
                "这款手机的电池容量是多少？",
                "有什么适合学生用的笔记本电脑？",
                "A品牌和B品牌的电视有什么区别？",
              ].map((q, i) => (
                <div
                  key={i}
                  onClick={() => handleSend(q)}
                  style={{
                    padding: "6px 12px",
                    margin: "4px 0",
                    background: themeToken.colorFillAlter,
                    borderRadius: 6,
                    cursor: "pointer",
                    fontSize: 13,
                    color: themeToken.colorTextSecondary,
                  }}
                >
                  💬 {q}
                </div>
              ))}
            </div>
          </div>
        </Empty>
        <div style={{ width: "100%", position: "absolute", bottom: 0 }}>
          <ChatInput onSend={handleSend} isStreaming={isStreaming} disabled={false} />
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* 消息列表 */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "24px",
        }}
      >
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          {messages.length === 0 && !isStreaming && (
            <div style={{ textAlign: "center", marginTop: 60, marginBottom: 40 }}>
              <Text type="secondary" style={{ fontSize: 15 }}>
                开始提问，获取基于知识库的智能回答
              </Text>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {/* 流式输出中的消息 */}
          {isStreaming && streamingContent && (
            <MessageBubble
              message={{
                id: 0,
                conversation_id: activeConversationId || 0,
                role: "assistant",
                content: streamingContent,
                created_at: new Date().toISOString(),
              }}
            />
          )}

          {/* 打字指示器 */}
          {isStreaming && !streamingContent && (
            <div style={{ textAlign: "center", padding: 16 }}>
              <Text type="secondary">
                <span className="typing-dots">AI 正在思考</span>...
              </Text>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 输入框 */}
      <ChatInput onSend={handleSend} onStop={stopStreaming} isStreaming={isStreaming} />
    </div>
  );
};

export default ChatPage;
