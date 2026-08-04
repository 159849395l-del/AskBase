/** 认证 API 调用 */

import apiClient from "./client";
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserInfo,
  ChangePasswordRequest,
} from "../types/auth";

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const formData = new FormData();
  formData.append("username", data.username);
  formData.append("password", data.password);
  const resp = await apiClient.post<TokenResponse>("/auth/login", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return resp.data;
}

export async function register(data: RegisterRequest): Promise<UserInfo> {
  const resp = await apiClient.post<UserInfo>("/auth/register", data);
  return resp.data;
}

export async function getMe(): Promise<UserInfo> {
  const resp = await apiClient.get<UserInfo>("/auth/me");
  return resp.data;
}

export async function changePassword(data: ChangePasswordRequest): Promise<{ message: string }> {
  const resp = await apiClient.put<{ message: string }>("/auth/change-password", data);
  return resp.data;
}
