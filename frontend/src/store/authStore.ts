/** 认证状态管理 */

import { create } from "zustand";
import type { UserInfo } from "../types/auth";
import { login as apiLogin, register as apiRegister, getMe } from "../api/auth";

interface AuthState {
  user: UserInfo | null;
  token: string | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  loading: boolean;

  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, confirmPassword: string) => Promise<void>;
  logout: () => void;
  fetchCurrentUser: () => Promise<void>;
  initialize: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: localStorage.getItem("access_token"),
  isAuthenticated: !!localStorage.getItem("access_token"),
  isAdmin: false,
  loading: false,

  login: async (username, password) => {
    set({ loading: true });
    try {
      const resp = await apiLogin({ username, password });
      localStorage.setItem("access_token", resp.access_token);
      localStorage.setItem("user_info", JSON.stringify(resp.user));
      set({
        token: resp.access_token,
        user: resp.user,
        isAuthenticated: true,
        isAdmin: resp.user.role === "admin",
        loading: false,
      });
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  register: async (username, password, confirmPassword) => {
    set({ loading: true });
    try {
      await apiRegister({ username, password, confirm_password: confirmPassword });
      set({ loading: false });
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_info");
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      isAdmin: false,
    });
  },

  fetchCurrentUser: async () => {
    try {
      const user = await getMe();
      localStorage.setItem("user_info", JSON.stringify(user));
      set({
        user,
        isAuthenticated: true,
        isAdmin: user.role === "admin",
      });
    } catch {
      get().logout();
    }
  },

  initialize: () => {
    const token = localStorage.getItem("access_token");
    const cachedUser = localStorage.getItem("user_info");
    if (token && cachedUser) {
      try {
        const user = JSON.parse(cachedUser) as UserInfo;
        set({
          token,
          user,
          isAuthenticated: true,
          isAdmin: user.role === "admin",
        });
        // 后台刷新用户信息
        get().fetchCurrentUser();
      } catch {
        get().logout();
      }
    }
  },
}));
