/** 会话列表组件：每条只显示标题一行，默认 6 条，更多收进「查看更多」 */

import React, { useState } from "react";
import { List, Typography, Button, Popconfirm, theme } from "antd";
import { DeleteOutlined, MessageOutlined, DownOutlined, UpOutlined } from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import { useChatStore } from "../../store/chatStore";

const { Text } = Typography;

const MAX_VISIBLE = 6;

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

  const [showAll, setShowAll] = useState(false);

  const handleSelect = async (convId: number) => {
    await setActiveConversation(convId);
    navigate(`/chat/${convId}`);
  };

  const hasMore = conversations.length > MAX_VISIBLE;
  const visibleConvs = showAll ? conversations : conversations.slice(0, MAX_VISIBLE);
  const hiddenCount = conversations.length - MAX_VISIBLE;

  return (
    <>
      <List
        loading={loadingConversations}
        dataSource={visibleConvs}
        locale={{ emptyText: "暂无会话" }}
        renderItem={(item) => {
          const isActive = item.id === activeId;
          return (
            <List.Item
              key={item.id}
              onClick={() => handleSelect(item.id)}
              style={{
                cursor: "pointer",
                padding: collapsed ? "10px 8px" : "10px 16px",
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
                avatar={<MessageOutlined style={{ fontSize: 16, color: themeToken.colorPrimary }} />}
                title={
                  <Text
                    ellipsis
                    style={{ maxWidth: collapsed ? 120 : 180, fontWeight: isActive ? 500 : 400, fontSize: 13, lineHeight: "20px", display: "block" }}
                  >
                    {item.title || `会话 #${item.id}`}
                  </Text>
                }
              />
            </List.Item>
          );
        }}
      />
      {!collapsed && hasMore && (
        <div style={{ padding: "4px 16px 8px", textAlign: "center" }}>
          <Button
            type="text"
            size="small"
            style={{ fontSize: 12, color: themeToken.colorPrimary }}
            icon={showAll ? <UpOutlined /> : <DownOutlined />}
            onClick={() => setShowAll((v) => !v)}
          >
            {showAll ? "收起" : `查看更多（${hiddenCount}）`}
          </Button>
        </div>
      )}
    </>
  );
};

export default ConversationList;
