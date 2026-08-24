/** B 类（数据库型）知识库子资源 API 调用：表信息 / 字段 / 知识点 */

import apiClient from "./client";
import type {
  DBTableItem,
  DBKnowledgePoint,
  DBKnowledgePointForm,
  DBKnowledgePointListResponse,
} from "../types/dbkb";

/* ---------- 表信息 ---------- */

export async function listTables(kbId: number): Promise<DBTableItem[]> {
  const resp = await apiClient.get<DBTableItem[]>(`/knowledge-bases/${kbId}/tables`);
  return resp.data;
}

export async function syncTables(kbId: number): Promise<{ message: string }> {
  const resp = await apiClient.post<{ message: string }>(`/knowledge-bases/${kbId}/tables/sync`);
  return resp.data;
}

export async function updateTable(
  kbId: number,
  tableId: number,
  patch: { table_comment?: string; is_required?: boolean }
): Promise<DBTableItem> {
  const resp = await apiClient.put<DBTableItem>(`/knowledge-bases/${kbId}/tables/${tableId}`, patch);
  return resp.data;
}

export async function deleteTable(kbId: number, tableId: number): Promise<void> {
  await apiClient.delete(`/knowledge-bases/${kbId}/tables/${tableId}`);
}

/* ---------- 字段 ---------- */

export async function updateField(
  kbId: number,
  tableId: number,
  fieldId: number,
  patch: { field_comment?: string; is_required?: boolean; status?: string }
): Promise<DBTableItem> {
  const resp = await apiClient.put<DBTableItem>(
    `/knowledge-bases/${kbId}/tables/${tableId}/fields/${fieldId}`,
    patch
  );
  return resp.data;
}

export async function deleteField(kbId: number, tableId: number, fieldId: number): Promise<void> {
  await apiClient.delete(`/knowledge-bases/${kbId}/tables/${tableId}/fields/${fieldId}`);
}

/* ---------- 知识点 ---------- */

export async function listKnowledgePoints(
  kbId: number,
  page = 1,
  pageSize = 20
): Promise<DBKnowledgePointListResponse> {
  const resp = await apiClient.get<DBKnowledgePointListResponse>(
    `/knowledge-bases/${kbId}/knowledge-points`,
    { params: { page, page_size: pageSize } }
  );
  return resp.data;
}

export async function createKnowledgePoint(
  kbId: number,
  form: DBKnowledgePointForm
): Promise<DBKnowledgePoint> {
  const resp = await apiClient.post<DBKnowledgePoint>(`/knowledge-bases/${kbId}/knowledge-points`, form);
  return resp.data;
}

export async function updateKnowledgePoint(
  kbId: number,
  kpId: number,
  form: Partial<DBKnowledgePointForm>
): Promise<DBKnowledgePoint> {
  const resp = await apiClient.put<DBKnowledgePoint>(`/knowledge-bases/${kbId}/knowledge-points/${kpId}`, form);
  return resp.data;
}

export async function deleteKnowledgePoint(kbId: number, kpId: number): Promise<void> {
  await apiClient.delete(`/knowledge-bases/${kbId}/knowledge-points/${kpId}`);
}
