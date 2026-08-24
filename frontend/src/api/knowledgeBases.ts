/** 知识库管理 API 调用 */

import apiClient from "./client";
import type {
  KnowledgeBaseItem,
  KnowledgeBaseForm,
  UserBrief,
} from "../types/kb";

export async function listKnowledgeBases(): Promise<KnowledgeBaseItem[]> {
  const resp = await apiClient.get<KnowledgeBaseItem[]>("/knowledge-bases");
  return resp.data;
}

export async function getKnowledgeBase(id: number): Promise<KnowledgeBaseItem> {
  const resp = await apiClient.get<KnowledgeBaseItem>(`/knowledge-bases/${id}`);
  return resp.data;
}

export async function createKnowledgeBase(
  form: KnowledgeBaseForm
): Promise<KnowledgeBaseItem> {
  const resp = await apiClient.post<KnowledgeBaseItem>("/knowledge-bases", form);
  return resp.data;
}

export async function updateKnowledgeBase(
  id: number,
  form: Partial<KnowledgeBaseForm>
): Promise<KnowledgeBaseItem> {
  const resp = await apiClient.put<KnowledgeBaseItem>(`/knowledge-bases/${id}`, form);
  return resp.data;
}

export async function deleteKnowledgeBase(id: number): Promise<void> {
  await apiClient.delete(`/knowledge-bases/${id}`);
}

/** 用户列表（授权用户下拉） */
export async function listUsers(): Promise<UserBrief[]> {
  const resp = await apiClient.get<UserBrief[]>("/auth/users");
  return resp.data;
}
