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
        requests: 2,
        llm_calls: 5,
        prompt_tokens: 100,
        completion_tokens: 40,
        total_tokens: 140,
      },
      excluded: { estimated_calls: 1 },
    };
    mockedGet.mockResolvedValue({ data: payload });

    const result = await getUsageOverview({ start: "2026-09-01", end: "2026-09-30" });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/overview", {
      params: { start: "2026-09-01", end: "2026-09-30" },
    });
    expect(result).toEqual(payload);
    // 两个计数与被排除的估算数都要原样透传，前端才能如实呈现口径
    expect(result.totals.requests).toBe(2);
    expect(result.totals.llm_calls).toBe(5);
    expect(result.excluded.estimated_calls).toBe(1);
  });

  it("场景：接口返回空区间 → 合计为全零而不是 null", async () => {
    mockedGet.mockResolvedValue({
      data: {
        start: "2026-01-01",
        end: "2026-01-31",
        totals: {
          requests: 0,
          llm_calls: 0,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
        excluded: { estimated_calls: 0 },
      },
    });

    const result = await getUsageOverview({ start: "2026-01-01", end: "2026-01-31" });

    expect(result.totals.total_tokens).toBe(0);
  });
});
