/** 聊天相关类型 */

export interface SourceItem {
  filename: string;
  chunk_text: string;
  similarity_score: number;
  chunk_index: number;
  product_category: string | null;
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
  message_count: number;
  last_message_preview?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: number;
  title: string;
  is_active: boolean;
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
