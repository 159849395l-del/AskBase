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
  status?: string
): Promise<DocumentListResponse> {
  const resp = await apiClient.get<DocumentListResponse>("/kb/documents", {
    params: { page, page_size: pageSize, status },
  });
  return resp.data;
}

export async function uploadDocument(
  file: File
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
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

/** 同步爬虫（ai_crawl）数据到知识库：读 MySQL → 切分 → 摄入 ChromaDB（幂等增量） */
export async function ingestCrawlData(): Promise<{ message: string }> {
  const resp = await apiClient.post<{ message: string }>("/kb/ingest-crawl", {}, { timeout: 600000 });
  return resp.data;
}
