/** 会话列表组件 */

import React from "react";
import { List, Typography, Button, Popconfirm, theme } from "antd";
import { DeleteOutlined, MessageOutlined } from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import dayjs from "dayjs";
import { useChatStore } from "../../store/chatStore";

const { Text } = Typography;

interface ConversationListProps {
  collapsed: boolean;
}

const ConversationList: React.FC<ConversationListProps> = ({ collapsed }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const conversations = useChatStore((s) => s.conversations);
  const activeId = useChatStore((s) => s.activeConversationId);
  const setActiveConversation = useChatStore((s) => s.setActiveConversation);
  const removeConversation = useChatStore((s) => s.removeConversation);
  const loadingConversations = useChatStore((s) => s.loadingConversations);
  const { token: themeToken } = theme.useToken();

  const handleSelect = async (convId: number) => {
    await setActiveConversation(convId);
    navigate(`/chat/${convId}`);
  };

  return (
    <List
      loading={loadingConversations}
      dataSource={conversations}
      locale={{ emptyText: "暂无会话" }}
      renderItem={(item) => {
        const isActive = item.id === activeId;
        return (
          <List.Item
            key={item.id}
            onClick={() => handleSelect(item.id)}
            style={{
              cursor: "pointer",
              padding: collapsed ? "12px 8px" : "12px 16px",
              background: isActive ? themeToken.colorPrimaryBg : "transparent",
              borderInlineEnd: isActive ? `3px solid ${themeToken.colorPrimary}` : "3px solid transparent",
              transition: "background 0.2s",
            }}
            extra={
              !collapsed && (
                <Popconfirm
                  title="确定删除此会话？"
                  onConfirm={(e) => {
                    e?.stopPropagation();
                    removeConversation(item.id);
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                >
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              )
            }
          >
            <List.Item.Meta
              avatar={<MessageOutlined style={{ fontSize: 18, color: themeToken.colorPrimary }} />}
              title={
                !collapsed && (
                  <Text ellipsis style={{ maxWidth: 200, fontWeight: isActive ? 600 : 400 }}>
                    {item.title}
                  </Text>
                )
              }
              description={
                !collapsed && (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {item.last_message_preview || "点击开始对话"}
                    </Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {dayjs(item.updated_at).format("MM-DD HH:mm")} · {item.message_count} 条
                    </Text>
                  </div>
                )
              }
            />
          </List.Item>
        );
      }}
    />
  );
};

export default ConversationList;
