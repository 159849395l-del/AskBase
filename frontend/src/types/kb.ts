/** 知识库管理相关类型 */

export interface DocumentItem {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: "processing" | "indexed" | "failed";
  product_category: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface KBStatsResponse {
  total_documents: number;
  total_chunks: number;
  total_size_bytes: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  last_ingested_at: string | null;
}
