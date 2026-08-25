/** 用户管理 API 调用 */

import apiClient from "./client";

export interface AdminUserItem {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUserCreate {
  username: string;
  password: string;
  role: string;
}

export interface AdminUserUpdate {
  role?: string;
  is_active?: boolean;
}

export async function listAdminUsers(): Promise<AdminUserItem[]> {
  const resp = await apiClient.get<AdminUserItem[]>("/admin/users");
  return resp.data;
}

export async function createAdminUser(
  form: AdminUserCreate
): Promise<AdminUserItem> {
  const resp = await apiClient.post<AdminUserItem>("/admin/users", form);
  return resp.data;
}

export async function updateAdminUser(
  id: number,
  form: AdminUserUpdate
): Promise<AdminUserItem> {
  const resp = await apiClient.put<AdminUserItem>(`/admin/users/${id}`, form);
  return resp.data;
}

export async function resetUserPassword(
  id: number,
  new_password: string
): Promise<{ message: string }> {
  const resp = await apiClient.put(`/admin/users/${id}/password`, { new_password });
  return resp.data;
}

export async function deleteAdminUser(id: number): Promise<{ message: string }> {
  const resp = await apiClient.delete(`/admin/users/${id}`);
  return resp.data;
}
