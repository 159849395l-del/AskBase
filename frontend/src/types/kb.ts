/** 知识库管理相关类型 */

export type KnowledgeBaseType = "document" | "database";

export interface KnowledgeBaseItem {
  id: number;
  name: string;
  label: string;
  authorized_user_id: number | null;
  type: KnowledgeBaseType;
  data_source_id: number | null;
  database_name: string | null;
  description: string;
  created_at: string;
  updated_at: string;
  // 富信息
  data_source_name?: string | null;
  doc_count: number;
  qa_count: number;
  table_count: number;
  kp_count: number;
}

export interface KnowledgeBaseForm {
  name: string;
  label: string;
  authorized_user_id?: number | null;
  type: KnowledgeBaseType;
  data_source_id?: number | null;
  database_name?: string;
  description: string;
}

export interface UserBrief {
  id: number;
  username: string;
  role: string;
}

export interface DocumentItem {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: "processing" | "indexed" | "failed";
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
  by_status: Record<string, number>;
  last_ingested_at: string | null;
}

export interface QAItem {
  id: number;
  kb_id: number;
  question: string;
  answer: string;
  created_at: string;
  updated_at: string;
}

export interface QAItemForm {
  kb_id: number;
  question: string;
  answer: string;
}

export interface QAItemListResponse {
  items: QAItem[];
  total: number;
}
