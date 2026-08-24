/** 数据源管理 API 调用 */

import apiClient from "./client";
import type {
  DataSourceItem,
  DataSourceForm,
  TestConnectionResponse,
} from "../types/datasource";

export async function listDataSources(): Promise<DataSourceItem[]> {
  const resp = await apiClient.get<DataSourceItem[]>("/data-sources");
  return resp.data;
}

export async function createDataSource(
  form: DataSourceForm
): Promise<DataSourceItem> {
  const resp = await apiClient.post<DataSourceItem>("/data-sources", form);
  return resp.data;
}

export async function updateDataSource(
  id: number,
  form: Partial<DataSourceForm>
): Promise<DataSourceItem> {
  const resp = await apiClient.put<DataSourceItem>(`/data-sources/${id}`, form);
  return resp.data;
}

export async function deleteDataSource(id: number): Promise<void> {
  await apiClient.delete(`/data-sources/${id}`);
}

/** 用表单里填的连接信息测试连通（不落库） */
export async function testDataSourceConnection(
  form: DataSourceForm
): Promise<TestConnectionResponse> {
  const resp = await apiClient.post<TestConnectionResponse>(
    "/data-sources/test-connection",
    form
  );
  return resp.data;
}
