/** 数据源管理相关类型 */

export interface DataSourceItem {
  id: number;
  name: string;
  type: string;
  host: string;
  port: number;
  database: string;
  username: string;
  created_at: string;
  updated_at: string;
}

/** 新建/编辑表单数据（password 仅入参） */
export interface DataSourceForm {
  name: string;
  type: string;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  latency_ms?: number | null;
}
