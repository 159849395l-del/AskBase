/** authStore 单元测试 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { useAuthStore } from "./authStore";

// Mock API 调用
vi.mock("../api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
}));

import * as authApi from "../api/auth";

describe("authStore — 认证状态管理", () => {
  beforeEach(() => {
    // 重置状态
    localStorage.clear();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isAdmin: false,
      loading: false,
    });
    vi.clearAllMocks();
  });

  describe("登录 (login)", () => {
    it("登录成功：设置 user、token、isAuthenticated、isAdmin", async () => {
      const mockUser = { id: 1, username: "admin", role: "admin", created_at: "2024-01-01" };
      const mockToken = "jwt-token-abc";
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: mockToken,
        token_type: "bearer",
        user: mockUser,
      });

      await useAuthStore.getState().login("admin", "123456");

      const state = useAuthStore.getState();
      expect(state.token).toBe(mockToken);
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAdmin).toBe(true);
      expect(state.loading).toBe(false);
      expect(localStorage.getItem("access_token")).toBe(mockToken);
    });

    it("登录成功：普通用户 isAdmin 为 false", async () => {
      vi.mocked(authApi.login).mockResolvedValue({
        access_token: "token",
        token_type: "bearer",
        user: { id: 2, username: "user1", role: "user", created_at: "2024-01-01" },
      });

      await useAuthStore.getState().login("user1", "123456");

      const state = useAuthStore.getState();
      expect(state.isAdmin).toBe(false);
      expect(state.isAuthenticated).toBe(true);
    });

    it("登录失败：设置 loading=false，不改变认证状态", async () => {
      vi.mocked(authApi.login).mockRejectedValue(new Error("用户名或密码错误"));

      await expect(
        useAuthStore.getState().login("admin", "wrong")
      ).rejects.toThrow();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.token).toBeNull();
      expect(state.loading).toBe(false);
    });
  });

  describe("注册 (register)", () => {
    it("注册成功：loading 重置为 false", async () => {
      vi.mocked(authApi.register).mockResolvedValue({
        id: 3,
        username: "newuser",
        role: "user",
        created_at: "2024-01-01",
      });

      await useAuthStore.getState().register("newuser", "123456", "123456");

      expect(useAuthStore.getState().loading).toBe(false);
    });

    it("注册失败：抛出错误，loading 重置", async () => {
      vi.mocked(authApi.register).mockRejectedValue({
        response: { data: { detail: "用户名已存在" } },
      });

      await expect(
        useAuthStore.getState().register("admin", "123456", "123456")
      ).rejects.toBeDefined();

      expect(useAuthStore.getState().loading).toBe(false);
    });
  });

  describe("登出 (logout)", () => {
    it("登出：清除所有状态和 localStorage", async () => {
      // 先设置为已登录
      useAuthStore.setState({
        token: "some-token",
        user: { id: 1, username: "admin", role: "admin", created_at: "" },
        isAuthenticated: true,
        isAdmin: true,
      });
      localStorage.setItem("access_token", "some-token");
      localStorage.setItem("user_info", JSON.stringify({ id: 1 }));

      useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.token).toBeNull();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isAdmin).toBe(false);
      expect(localStorage.getItem("access_token")).toBeNull();
      expect(localStorage.getItem("user_info")).toBeNull();
    });
  });

  describe("初始化 (initialize)", () => {
    it("无缓存 token：保持未登录状态", () => {
      localStorage.removeItem("access_token");

      useAuthStore.getState().initialize();

      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    });

    it("有缓存 token 和 user：恢复登录状态", () => {
      localStorage.setItem("access_token", "cached-token");
      localStorage.setItem(
        "user_info",
        JSON.stringify({ id: 1, username: "admin", role: "admin", created_at: "" })
      );

      useAuthStore.getState().initialize();

      const state = useAuthStore.getState();
      expect(state.token).toBe("cached-token");
      expect(state.isAuthenticated).toBe(true);
      expect(state.isAdmin).toBe(true);
      expect(state.user?.username).toBe("admin");
    });

    it("缓存 user 非 admin：isAdmin 为 false", () => {
      localStorage.setItem("access_token", "token");
      localStorage.setItem(
        "user_info",
        JSON.stringify({ id: 2, username: "user1", role: "user", created_at: "" })
      );

      useAuthStore.getState().initialize();

      expect(useAuthStore.getState().isAdmin).toBe(false);
    });
  });
});
