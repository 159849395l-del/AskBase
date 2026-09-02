/** 智能体相关类型 */

/** 智能体挂载的工具引用 */
export interface AgentToolRef {
  tool_type: "skill" | "mcp_tool";
  /** 内部 Skill 的 id（tool_type=skill） */
  tool_ref_id?: number | null;
  /** MCP 工具引用 "<server_id>:<tool_name>"（tool_type=mcp_tool） */
  tool_ref?: string | null;
  enabled: boolean;
}

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
  kb_ids: number[];
  model_id?: number | null;
  tools?: AgentToolRef[];
}

export interface AgentDetail extends AgentItem {
  system_prompt: string;
  updated_at: string;
  tools: AgentToolRef[];
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
  kb_ids?: number[];
  model_id?: number | null;
  tools?: AgentToolRef[];
}
