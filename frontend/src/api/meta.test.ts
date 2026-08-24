/** meta API 单元测试 — 品类列表 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import apiClient from "./client";
import { fetchCategories } from "./meta";

// Mock axios 客户端
vi.mock("./client", () => ({
  default: { get: vi.fn() },
}));

describe("fetchCategories — 商品品类列表", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("请求成功：返回品类数组", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { categories: ["羽绒服", "手机", "笔记本电脑"] },
    } as any);

    const result = await fetchCategories();

    expect(result).toEqual(["羽绒服", "手机", "笔记本电脑"]);
    expect(apiClient.get).toHaveBeenCalledWith("/categories");
  });

  it("响应缺 categories 字段：返回空数组", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} } as any);

    const result = await fetchCategories();

    expect(result).toEqual([]);
  });

  it("请求失败：静默返回空数组，不抛出异常", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("网络错误"));

    const result = await fetchCategories();

    expect(result).toEqual([]);
  });
});
