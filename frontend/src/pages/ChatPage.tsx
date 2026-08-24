/** 聊天主页面：无会话时显示智能体卡片入口；会话内支持智能体欢迎语 */

import React, { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Typography, Empty, Card, Row, Col, Spin, Button, theme } from "antd";
import { RobotOutlined, ArrowLeftOutlined } from "@ant-design/icons";
import { useChatStore } from "../store/chatStore";
import { useAuthStore } from "../store/authStore";
import { listAgents, getOrCreateAgentConversation } from "../api/agent";
import { listDocuments } from "../api/kb";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";
import type { AgentItem } from "../types/agent";

const { Title, Text } = Typography;

const ChatPage: React.FC = () => {
  const { convId } = useParams<{ convId?: string }>();
  const navigate = useNavigate();
  const messages = useChatStore((s) => s.messages);
  const streamingContent = useChatStore((s) => s.streamingContent);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const activeConversationId = useChatStore((s) => s.activeConversationId);
  const activeAgentId = useChatStore((s) => s.activeAgentId);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const stopStreaming = useChatStore((s) => s.stopStreaming);
  const clearActiveConversation = useChatStore((s) => s.clearActiveConversation);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const { token: themeToken } = theme.useToken();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 路由主导：/chat（无 convId）= 智能体列表；/chat/:convId = 会话
  const convIdNum = convId ? parseInt(convId, 10) : null;
  const isOnListPage = !convIdNum;

  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<AgentItem | null>(null);
  // 管理员普通会话（未绑定智能体）用的知识库选择器数据
  const [adminKbs, setAdminKbs] = useState<{ id: number; name: string }[]>([]);

  // 拉取智能体列表（所有人）
  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch(() => setAgents([]))
      .finally(() => setAgentsLoading(false));
  }, []);

  // 管理员才拉取知识库（普通用户不显示选择器）
  useEffect(() => {
    if (!isAdmin) return;
    listDocuments(1, 100)
      .then((resp) => setAdminKbs(resp.items.map((d) => ({ id: d.id, name: d.filename }))))
      .catch(() => {});
  }, [isAdmin]);

  // 进入会话：加载该会话（含绑定的智能体）
  useEffect(() => {
    if (convIdNum && convIdNum !== activeConversationId) {
      setActiveConversation(convIdNum);
    }
  }, [convIdNum]);

  // 回到列表页（/chat）：清空激活状态，否则页面会一直停留在旧会话
  useEffect(() => {
    if (isOnListPage && activeConversationId !== null) {
      clearActiveConversation();
    }
  }, [isOnListPage, activeConversationId, clearActiveConversation]);

  // 当前会话绑定的智能体详情（用于欢迎语）
  useEffect(() => {
    if (activeAgentId && agents.length > 0) {
      setActiveAgent(agents.find((a) => a.id === activeAgentId) || null);
    } else {
      setActiveAgent(null);
    }
  }, [activeAgentId, agents]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  const handleSend = async (content: string, kbDocIds?: number[]) => {
    if (!activeConversationId) {
      // 无会话时（不应到达这里：入口必须点智能体卡片）
      const { createNewConversation, setActiveConversation } = useChatStore.getState();
      const newId = await createNewConversation();
      await setActiveConversation(newId);
      navigate(`/chat/${newId}`, { replace: true });
      setTimeout(() => {
        useChatStore.getState().sendMessage(content, kbDocIds);
      }, 100);
    } else {
      // agent 会话由后端注入设置；普通会话传前端选择的知识库
      const viaAgent = !!activeAgentId;
      await sendMessage(content, viaAgent ? undefined : kbDocIds);
    }
  };

  // 点击智能体卡片：取或建该用户对该智能体的会话（同一智能体保持一个会话，复用继续聊）
  const handleAgentClick = async (agent: AgentItem) => {
    const { setActiveConversation } = useChatStore.getState();
    const conv = await getOrCreateAgentConversation(agent.id);
    await setActiveConversation(conv.id);
    navigate(`/chat/${conv.id}`);
  };

  // ---------- 智能体卡片入口（路由 /chat，无 convId）----------
  if (isOnListPage) {
    return (
      <div style={{ height: "100%", overflow: "auto", padding: 24 }}>
        <div style={{ maxWidth: 1000, margin: "0 auto" }}>
          <div style={{ textAlign: "center", marginTop: 16, marginBottom: 28 }}>
            <Title level={3} style={{ marginBottom: 4 }}>
              请选择一个智能体开始对话
            </Title>
            <Text type="secondary">每个智能体都有专属的知识库与回答风格</Text>
          </div>

          {agentsLoading ? (
            <div style={{ textAlign: "center", padding: 60 }}>
              <Spin />
            </div>
          ) : agents.length === 0 ? (
            <Empty
              image={<RobotOutlined style={{ fontSize: 64, color: themeToken.colorPrimary }} />}
              description={
                <div>
                  <Title level={4}>暂无可用智能体</Title>
                  <Text type="secondary">请联系管理员在后台配置智能体</Text>
                </div>
              }
            />
          ) : (
            <Row gutter={[16, 16]}>
              {agents.map((agent) => (
                <Col xs={24} sm={12} md={8} lg={6} key={agent.id}>
                  <Card
                    hoverable
                    style={{ borderRadius: 12, textAlign: "center", padding: "8px 0" }}
                    onClick={() => handleAgentClick(agent)}
                  >
                    <div style={{ fontSize: 40, marginBottom: 8 }}>{agent.icon || <RobotOutlined />}</div>
                    <div style={{ fontWeight: 500, fontSize: 15, marginBottom: 6 }}>{agent.name}</div>
                    <div
                      style={{
                        color: themeToken.colorTextSecondary,
                        fontSize: 12,
                        height: 32,
                        overflow: "hidden",
                      }}
                    >
                      {agent.description || agent.welcome_message}
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </div>
      </div>
    );
  }

  // ---------- 会话内 ----------
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* 会话顶部导航条 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 24px",
          borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          background: themeToken.colorBgContainer,
        }}
      >
        <Button type="text" size="small" icon={<ArrowLeftOutlined />} onClick={() => navigate("/chat")}>
          返回智能体列表
        </Button>
        {activeAgent && (
          <span style={{ fontSize: 14, fontWeight: 500 }}>
            {activeAgent.icon} {activeAgent.name}
          </span>
        )}
      </div>

      {/* 消息列表 */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "24px",
        }}
      >
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          {/* 智能体欢迎语（无消息时） */}
          {messages.length === 0 && !isStreaming && activeAgent && (
            <div style={{ textAlign: "center", marginTop: 48, marginBottom: 40 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>{activeAgent.icon}</div>
              <Title level={4} style={{ marginBottom: 8 }}>
                {activeAgent.name}
              </Title>
              <Text type="secondary" style={{ fontSize: 14 }}>
                {activeAgent.welcome_message}
              </Text>
            </div>
          )}

          {messages.length === 0 && !isStreaming && !activeAgent && (
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

      {/* 输入框：agent 会话与普通用户隐藏知识库选择器 */}
      <ChatInput
        knowledgeBases={isAdmin && !activeAgentId ? adminKbs : []}
        onSend={handleSend}
        onStop={stopStreaming}
        isStreaming={isStreaming}
      />
    </div>
  );
};

export default ChatPage;
