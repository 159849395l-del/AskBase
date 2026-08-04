/** 认证相关类型 */

export interface UserInfo {
  id: number;
  username: string;
  role: "admin" | "user";
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserInfo;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  confirm_password: string;
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
  confirm_new_password: string;
}
