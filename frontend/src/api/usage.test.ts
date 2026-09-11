/** usage API 单元测试 — 请求地址、查询参数与返回值透传 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import apiClient from "./client";
import { getUsageOverview } from "./usage";

vi.mock("./client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

describe("getUsageOverview — 用量总览", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("场景：传入起止日期 → 请求 /admin/usage/overview 并原样带上参数与返回", async () => {
    const payload = {
      start: "2026-09-01",
      end: "2026-09-30",
      totals: {
        llm_calls: 3,
        prompt_tokens: 100,
        completion_tokens: 40,
        total_tokens: 140,
      },
    };
    mockedGet.mockResolvedValue({ data: payload });

    const result = await getUsageOverview({ start: "2026-09-01", end: "2026-09-30" });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/overview", {
      params: { start: "2026-09-01", end: "2026-09-30" },
    });
    expect(result).toEqual(payload);
  });

  it("场景：接口返回空区间 → 合计为全零而不是 null", async () => {
    mockedGet.mockResolvedValue({
      data: {
        start: "2026-01-01",
        end: "2026-01-31",
        totals: {
          llm_calls: 0,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
      },
    });

    const result = await getUsageOverview({ start: "2026-01-01", end: "2026-01-31" });

    expect(result.totals.total_tokens).toBe(0);
  });
});
