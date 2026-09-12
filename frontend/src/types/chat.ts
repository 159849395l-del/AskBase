/** 聊天相关类型 */

export interface SourceItem {
  filename: string;
  chunk_text?: string | null;
  /** 网页来源之间没有可比的相似度，后端不编造该值 —— 前端也不显示百分比 */
  similarity_score?: number | null;
  /** "vector"=向量相似度 | "bm25"=关键词匹配（非相似度）| "sql"=SQL 来源 | "web"=网页 */
  score_type?: string | null;
  chunk_index?: number;
  /** 来源类型：doc（文档/问答/知识点）| sql（生成查询）| db_result（查询结果）| web（网页） */
  kind?: string | null;
  /** 网页来源：标题（与 filename 同值，便于统一展示） */
  title?: string | null;
  /** 网页来源：可点击的链接 */
  url?: string | null;
  snippet?: string | null;
  published?: string | null;
  /** SQL 来源时携带完整 SQL 语句 */
  sql?: string | null;
}

/** 一次工具调用（刷新页面后仍能从历史消息读回） */
export interface ToolCallItem {
  name: string;
  content: string;
}

export interface MessageItem {
  id: number;
  conversation_id: number;
  role: "user" | "assistant" | "system";
  content: string;
  sources?: SourceItem[] | null;
  tool_calls?: ToolCallItem[] | null;
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
