/** 知识库管理 API 调用 */

import apiClient from "./client";
import type {
  DocumentItem,
  DocumentListResponse,
  KBStatsResponse,
} from "../types/kb";

export async function listDocuments(
  page = 1,
  pageSize = 20,
  status?: string,
  category?: string
): Promise<DocumentListResponse> {
  const resp = await apiClient.get<DocumentListResponse>("/kb/documents", {
    params: { page, page_size: pageSize, status, category },
  });
  return resp.data;
}

export async function uploadDocument(
  file: File,
  productCategory?: string
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  if (productCategory) {
    formData.append("product_category", productCategory);
  }
  const resp = await apiClient.post<DocumentItem>("/kb/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000, // 上传+向量化可能需要较长时间
  });
  return resp.data;
}

export async function deleteDocument(docId: number): Promise<void> {
  await apiClient.delete(`/kb/documents/${docId}`);
}

export async function getKBStats(): Promise<KBStatsResponse> {
  const resp = await apiClient.get<KBStatsResponse>("/kb/stats");
  return resp.data;
}

export async function reindexKB(): Promise<{ message: string }> {
  const resp = await apiClient.post<{ message: string }>("/kb/reindex");
  return resp.data;
}
