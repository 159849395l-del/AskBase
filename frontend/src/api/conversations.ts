/** 会话 API 调用 */

import apiClient from "./client";
import type {
  ConversationItem,
  ConversationDetail,
  ConversationListResponse,
} from "../types/chat";

export async function listConversations(
  page = 1,
  pageSize = 20
): Promise<ConversationListResponse> {
  const resp = await apiClient.get<ConversationListResponse>("/conversations", {
    params: { page, page_size: pageSize },
  });
  return resp.data;
}

export async function createConversation(
  title?: string,
  agentId?: number
): Promise<ConversationItem> {
  const resp = await apiClient.post<ConversationItem>("/conversations", {
    title,
    agent_id: agentId,
  });
  return resp.data;
}

export async function getConversation(convId: number): Promise<ConversationDetail> {
  const resp = await apiClient.get<ConversationDetail>(`/conversations/${convId}`);
  return resp.data;
}

export async function deleteConversation(convId: number): Promise<void> {
  await apiClient.delete(`/conversations/${convId}`);
}

export async function updateConversationTitle(
  convId: number,
  title: string
): Promise<ConversationItem> {
  const resp = await apiClient.patch<ConversationItem>(
    `/conversations/${convId}`,
    { title }
  );
  return resp.data;
}
