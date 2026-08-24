/** 聊天输入框组件 */

import React, { useState, useRef, useEffect } from "react";
import { Input, Button, Select, Space, theme } from "antd";
import { SendOutlined, StopOutlined } from "@ant-design/icons";

const { TextArea } = Input;

interface KBOption {
  id: number;
  name: string;
}

interface ChatInputProps {
  /** 可选知识库列表（用于按 kb_doc_id 限定检索范围，空数组则不显示选择器） */
  knowledgeBases?: KBOption[];
  onSend: (content: string, kbDocIds?: number[]) => void;
  onStop?: () => void;
  isStreaming: boolean;
  disabled?: boolean;
}

const ChatInput: React.FC<ChatInputProps> = ({ knowledgeBases = [], onSend, onStop, isStreaming, disabled }) => {
  const [value, setValue] = useState("");
  const [kbDocIds, setKbDocIds] = useState<number[] | undefined>(undefined);
  const inputRef = useRef<any>(null);
  const { token: themeToken } = theme.useToken();

  useEffect(() => {
    if (!isStreaming && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isStreaming]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed, kbDocIds);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      style={{
        padding: "16px 24px",
        borderTop: `1px solid ${themeToken.colorBorderSecondary}`,
        background: themeToken.colorBgContainer,
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "flex-end",
          maxWidth: 900,
          margin: "0 auto",
        }}
      >
        {knowledgeBases.length > 0 && (
          <Select
            mode="multiple"
            allowClear
            placeholder="全部知识库"
            value={kbDocIds}
            onChange={(val) => setKbDocIds(val as number[])}
            options={knowledgeBases.map((kb) => ({ value: kb.id, label: kb.name }))}
            disabled={disabled}
            style={{ minWidth: 170, flexShrink: 0 }}
            maxTagCount="responsive"
          />
        )}
        <TextArea
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题，按 Enter 发送，Shift+Enter 换行..."
          autoSize={{ minRows: 1, maxRows: 6 }}
          disabled={disabled}
          style={{ borderRadius: 8, fontSize: 14 }}
        />
        <Space>
          {isStreaming ? (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={onStop}
              size="large"
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!value.trim() || disabled}
              size="large"
            >
              发送
            </Button>
          )}
        </Space>
      </div>
      <div style={{ textAlign: "center", marginTop: 6 }}>
        <span style={{ fontSize: 11, color: themeToken.colorTextQuaternary }}>
          回答基于知识库内容生成，可能存在偏差，请以实际商品信息为准
        </span>
      </div>
    </div>
  );
};

export default ChatInput;
