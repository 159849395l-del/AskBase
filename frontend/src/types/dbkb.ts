/** B 类（数据库型）知识库相关类型 */

export interface DBTableFieldItem {
  id: number;
  db_table_id: number;
  field_name: string;
  field_type: string;
  field_comment: string;
  is_required: boolean;
  status: "normal" | "conflict";
  created_at: string;
  updated_at: string;
}

export interface DBTableItem {
  id: number;
  kb_id: number;
  table_name: string;
  table_comment: string;
  column_count: number;
  is_required: boolean;
  status: "normal" | "conflict";
  created_at: string;
  updated_at: string;
  fields: DBTableFieldItem[];
}

export interface DBKnowledgePoint {
  id: number;
  kb_id: number;
  name: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface DBKnowledgePointForm {
  name: string;
  content: string;
}

export interface DBKnowledgePointListResponse {
  items: DBKnowledgePoint[];
  total: number;
}
