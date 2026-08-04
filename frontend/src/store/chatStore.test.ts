/** chatStore 单元测试 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { useChatStore } from "./chatStore";

// Mock API 调用
vi.mock("../api/conversations", () => ({
  listConversations: vi.fn(),
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  updateConversationTitle: vi.fn(),
}));

vi.mock("../api/chat", () => ({
  sendChatMessage: vi.fn(),
}));

import * as conversationsApi from "../api/conversations";

describe("chatStore — 聊天状态管理", () => {
  beforeEach(() => {
    useChatStore.setState({
      conversations: [],
      activeConversationId: null,
      messages: [],
      streamingContent: "",
      streamingSources: [],
      isStreaming: false,
      loadingConversations: false,
      abortController: null,
    });
    vi.clearAllMocks();
  });

  describe("会话列表 (fetchConversations)", () => {
    it("获取成功：填充 conversations 数组", async () => {
      const mockItems = [
        {
          id: 1,
          title: "测试会话",
          is_active: true,
          message_count: 3,
          created_at: "2024-01-01",
          updated_at: "2024-01-01",
        },
        {
          id: 2,
          title: "另一个会话",
          is_active: true,
          message_count: 1,
          created_at: "2024-01-02",
          updated_at: "2024-01-02",
        },
      ];
      vi.mocked(conversationsApi.listConversations).mockResolvedValue({
        items: mockItems,
        total: 2,
        page: 1,
        page_size: 20,
      });

      await useChatStore.getState().fetchConversations();

      const state = useChatStore.getState();
      expect(state.conversations).toHaveLength(2);
      expect(state.conversations[0].id).toBe(1);
      expect(state.conversations[0].title).toBe("测试会话");
      expect(state.loadingConversations).toBe(false);
    });

    it("获取失败：loadingConversations 重置为 false", async () => {
      vi.mocked(conversationsApi.listConversations).mockRejectedValue(new Error("网络错误"));

      await useChatStore.getState().fetchConversations();

      expect(useChatStore.getState().loadingConversations).toBe(false);
    });
  });

  describe("创建会话 (createNewConversation)", () => {
    it("创建成功：返回新会话 ID", async () => {
      vi.mocked(conversationsApi.createConversation).mockResolvedValue({
        id: 5,
        title: "新对话",
        is_active: true,
        message_count: 0,
        created_at: "2024-01-01",
        updated_at: "2024-01-01",
      });

      const convId = await useChatStore.getState().createNewConversation();

      expect(convId).toBe(5);
    });
  });

  describe("切换活跃会话 (setActiveConversation)", () => {
    it("切换会话：加载历史消息", async () => {
      const mockMessages = [
        {
          id: 1,
          conversation_id: 1,
          role: "user" as const,
          content: "你好",
          created_at: "2024-01-01",
        },
        {
          id: 2,
          conversation_id: 1,
          role: "assistant" as const,
          content: "你好！有什么可以帮助你的？",
          created_at: "2024-01-01",
        },
      ];
      vi.mocked(conversationsApi.getConversation).mockResolvedValue({
        id: 1,
        title: "测试",
        is_active: true,
        messages: mockMessages,
        created_at: "2024-01-01",
        updated_at: "2024-01-01",
      });

      await useChatStore.getState().setActiveConversation(1);

      const state = useChatStore.getState();
      expect(state.activeConversationId).toBe(1);
      expect(state.messages).toHaveLength(2);
      expect(state.messages[0].content).toBe("你好");
    });
  });

  describe("删除会话 (removeConversation)", () => {
    it("删除活跃会话：清除活跃状态", async () => {
      useChatStore.setState({ activeConversationId: 1, messages: [{ id: 1, conversation_id: 1, role: "user", content: "hi", created_at: "" }] });
      vi.mocked(conversationsApi.deleteConversation).mockResolvedValue(undefined);
      vi.mocked(conversationsApi.listConversations).mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
      });

      await useChatStore.getState().removeConversation(1);

      const state = useChatStore.getState();
      expect(state.activeConversationId).toBeNull();
      expect(state.messages).toHaveLength(0);
    });
  });

  describe("发送消息 (sendMessage)", () => {
    it("无活跃会话：不发送消息", async () => {
      await useChatStore.getState().sendMessage("hello");
      expect(useChatStore.getState().isStreaming).toBe(false);
    });

    it("正在流式输出中：不重复发送", async () => {
      useChatStore.setState({ activeConversationId: 1, isStreaming: true });
      await useChatStore.getState().sendMessage("another message");
      // 状态不变
      expect(useChatStore.getState().messages).toHaveLength(0);
    });
  });

  describe("流式状态管理 (streaming)", () => {
    it("stopStreaming 无流式输出：不执行操作", () => {
      const initialMessages = useChatStore.getState().messages;
      useChatStore.getState().stopStreaming();
      expect(useChatStore.getState().messages).toEqual(initialMessages);
    });

    it("clearMessages：清空消息和流式状态", () => {
      useChatStore.setState({
        messages: [{ id: 1, conversation_id: 1, role: "user", content: "hi", created_at: "" }],
        streamingContent: "partial",
        streamingSources: [{ filename: "test.md", chunk_text: "text", similarity_score: 0.9, chunk_index: 0, product_category: null }],
      });

      useChatStore.getState().clearMessages();

      expect(useChatStore.getState().messages).toHaveLength(0);
      expect(useChatStore.getState().streamingContent).toBe("");
      expect(useChatStore.getState().streamingSources).toHaveLength(0);
    });
  });
});
