/** 聊天状态管理 */

import { create } from "zustand";
import type { ConversationItem, MessageItem, SourceItem } from "../types/chat";
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  updateConversationTitle,
} from "../api/conversations";
import { sendChatMessage } from "../api/chat";

interface ChatState {
  conversations: ConversationItem[];
  activeConversationId: number | null;
  activeAgentId: number | null;
  messages: MessageItem[];
  streamingContent: string;
  streamingSources: SourceItem[];
  isStreaming: boolean;
  loadingConversations: boolean;
  abortController: AbortController | null;

  fetchConversations: () => Promise<void>;
  createNewConversation: (agentId?: number) => Promise<number>;
  setActiveConversation: (convId: number) => Promise<void>;
  removeConversation: (convId: number) => Promise<void>;
  renameConversation: (convId: number, title: string) => Promise<void>;
  sendMessage: (content: string, kbDocIds?: number[]) => Promise<void>;
  stopStreaming: () => void;
  clearMessages: () => void;
  clearActiveConversation: () => void;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  activeAgentId: null,
  messages: [],
  streamingContent: "",
  streamingSources: [],
  isStreaming: false,
  loadingConversations: false,
  abortController: null,

  fetchConversations: async () => {
    set({ loadingConversations: true });
    try {
      const resp = await listConversations(1, 50);
      set({ conversations: resp.items, loadingConversations: false });
    } catch {
      set({ loadingConversations: false });
    }
  },

  createNewConversation: async (agentId?: number) => {
    const conv = await createConversation(undefined, agentId);
    await get().fetchConversations();
    return conv.id;
  },

  setActiveConversation: async (convId: number) => {
    set({ activeConversationId: convId, messages: [], streamingContent: "", streamingSources: [] });
    try {
      const detail = await getConversation(convId);
      set({ messages: detail.messages, activeAgentId: detail.agent_id ?? null });
    } catch {
      // 会话不存在
    }
  },

  removeConversation: async (convId: number) => {
    await deleteConversation(convId);
    const state = get();
    if (state.activeConversationId === convId) {
      set({ activeConversationId: null, messages: [] });
    }
    await get().fetchConversations();
  },

  renameConversation: async (convId: number, title: string) => {
    await updateConversationTitle(convId, title);
    await get().fetchConversations();
  },

  sendMessage: async (content: string, kbDocIds?: number[]) => {
    const state = get();
    if (!state.activeConversationId || state.isStreaming) return;

    // 添加用户消息到本地
    const userMsg: MessageItem = {
      id: Date.now(),
      conversation_id: state.activeConversationId,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    set({
      messages: [...state.messages, userMsg],
      isStreaming: true,
      streamingContent: "",
      streamingSources: [],
    });

    let fullContent = "";

    const controller = sendChatMessage(
      state.activeConversationId,
      content,
      {
        onToken: (token) => {
          fullContent += token;
          set({ streamingContent: fullContent });
        },
        onSources: (sources) => {
          set({ streamingSources: sources });
        },
        onDone: (messageId, tokenCount) => {
          const assistantMsg: MessageItem = {
            id: messageId,
            conversation_id: state.activeConversationId!,
            role: "assistant",
            content: fullContent,
            sources: get().streamingSources,
            token_count: tokenCount,
            created_at: new Date().toISOString(),
          };
          set((s) => ({
            messages: [...s.messages, assistantMsg],
            streamingContent: "",
            isStreaming: false,
            abortController: null,
          }));
          // 刷新会话列表以更新标题
          get().fetchConversations();
        },
        onError: (error) => {
          const errorMsg: MessageItem = {
            id: Date.now(),
            conversation_id: state.activeConversationId!,
            role: "assistant",
            content: `❌ 回答生成失败: ${error}`,
            created_at: new Date().toISOString(),
          };
          set((s) => ({
            messages: [...s.messages, errorMsg],
            streamingContent: "",
            isStreaming: false,
            abortController: null,
          }));
        },
      },
      kbDocIds ?? undefined,
    );

    set({ abortController: controller });
  },

  stopStreaming: () => {
    const state = get();
    if (state.abortController) {
      state.abortController.abort();
    }
    // 保存已生成的部分
    if (state.streamingContent) {
      const partialMsg: MessageItem = {
        id: Date.now(),
        conversation_id: state.activeConversationId!,
        role: "assistant",
        content: state.streamingContent + "\n\n[用户终止回复]",
        sources: state.streamingSources,
        created_at: new Date().toISOString(),
      };
      set((s) => ({
        messages: [...s.messages, partialMsg],
        streamingContent: "",
        streamingSources: [],
        isStreaming: false,
        abortController: null,
      }));
    }
  },

  clearMessages: () => {
    set({ messages: [], streamingContent: "", streamingSources: [] });
  },

  // 退出当前会话（回到智能体列表页时调用），清空激活状态与消息
  clearActiveConversation: () => {
    set({
      activeConversationId: null,
      activeAgentId: null,
      messages: [],
      streamingContent: "",
      streamingSources: [],
      isStreaming: false,
      abortController: null,
    });
  },

  reset: () => {
    set({
      conversations: [],
      activeConversationId: null,
      activeAgentId: null,
      messages: [],
      streamingContent: "",
      streamingSources: [],
      isStreaming: false,
      abortController: null,
    });
  },
}));
