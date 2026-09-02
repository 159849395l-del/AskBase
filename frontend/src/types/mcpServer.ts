/** MCP 服务相关类型 */

export interface MCPToolItem {
  name: string;
  title: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface MCPServerItem {
  id: number;
  name: string;
  description: string;
  transport: "stdio" | "sse";
  is_active: boolean;
  tool_count: number;
  tools_cached_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCPServerDetail extends MCPServerItem {
  command?: string | null;
  /** JSON 字符串（参数数组） */
  args?: string | null;
  /** JSON 字符串（环境变量对象） */
  env?: string | null;
  url?: string | null;
  tools_cache?: string | null;
}

export interface MCPServerForm {
  name: string;
  description: string;
  transport: "stdio" | "sse";
  command?: string;
  args: string[];
  env: Record<string, string>;
  url?: string;
  is_active: boolean;
}

export interface DiscoverResponse {
  success: boolean;
  message: string;
  tools: MCPToolItem[];
}

export interface MCPToolCallResponse {
  success: boolean;
  result: string;
  message: string;
}
