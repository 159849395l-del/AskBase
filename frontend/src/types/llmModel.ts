/** 大模型库相关类型 */

export interface LLMModelItem {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  base_url: string;
  is_active: boolean;
  is_vision: boolean;
  supports_tool_call: boolean;
  is_default: boolean;
  temperature: number;
  max_tokens?: number | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

/** 新建/编辑表单（api_key 仅入参，不回显） */
export interface LLMModelForm {
  name: string;
  provider: string;
  model_id: string;
  base_url: string;
  api_key: string;
  is_active: boolean;
  is_vision: boolean;
  supports_tool_call: boolean;
  temperature: number;
  max_tokens?: number | null;
  sort_order: number;
  is_default?: boolean;
}

export interface ProviderOption {
  label: string;
  value: string;
  default_base_url: string;
}

export interface ModelTestResponse {
  success: boolean;
  message: string;
  latency_ms?: number | null;
}

export const PROVIDER_LABELS: Record<string, string> = {
  deepseek: "深度求索 DeepSeek",
  volcengine: "字节豆包 火山方舟",
  aliyun: "阿里云百炼",
  openai: "OpenAI",
  moonshot: "月之暗面 Kimi",
  zhipu: "智谱 GLM",
  local: "本地 / Ollama",
  custom: "自定义",
};
