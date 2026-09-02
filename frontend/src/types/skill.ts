/** 内部 Skill（AI 智能工具）相关类型 */

export interface SkillItem {
  id: number;
  name: string;
  title: string;
  description: string;
  icon: string;
  handler: string;
  input_schema: Record<string, unknown>;
  is_active: boolean;
  is_builtin: boolean;
  is_dangerous: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface SkillForm {
  name: string;
  title: string;
  description: string;
  icon: string;
  handler: string;
  // JSON Schema 结构不固定，用 any 避免与 antd Form 的泛型推断冲突
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  input_schema: Record<string, any>;
  is_active: boolean;
  is_dangerous: boolean;
  sort_order: number;
}

export interface SkillTestResponse {
  success: boolean;
  result: string;
  message: string;
}
