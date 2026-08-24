/** 聊天相关类型 */

export interface SourceItem {
  filename: string;
  chunk_text: string;
  similarity_score: number;
  /** "vector"=向量相似度 | "bm25"=关键词匹配（非相似度，前端不显示百分比）| "sql"=SQL 来源 */
  score_type?: string | null;
  chunk_index: number;
  /** 来源类型：doc（文档/问答/知识点）| sql（生成查询）| db_result（查询结果） */
  kind?: string | null;
  /** SQL 来源时携带完整 SQL 语句 */
  sql?: string | null;
}

export interface MessageItem {
  id: number;
  conversation_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: SourceItem[] | null;
  token_count?: number | null;
  created_at: string;
}

export interface ConversationItem {
  id: number;
  title: string;
  is_active: boolean;
  agent_id?: number | null;
  message_count: number;
  last_message_preview?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string;
  is_active: boolean;
  agent_id?: number | null;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

export interface ConversationListResponse {
  items: ConversationItem[];
  total: number;
  page: number;
  page_size: number;
}
