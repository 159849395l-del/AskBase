/** 智能体相关类型 */

export interface AgentItem {
  id: number;
  name: string;
  description: string;
  icon: string;
  welcome_message: string;
  is_active: boolean;
  is_hidden: boolean;
  sort_order: number;
  created_at: string;
  kb_doc_ids: number[];
}

export interface AgentDetail extends AgentItem {
  system_prompt: string;
  updated_at: string;
}

export interface AgentPayload {
  name: string;
  description?: string;
  icon?: string;
  welcome_message?: string;
  system_prompt?: string;
  is_active?: boolean;
  is_hidden?: boolean;
  sort_order?: number;
  kb_doc_ids?: number[];
}
