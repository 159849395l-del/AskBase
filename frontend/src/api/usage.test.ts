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
      agents: [
        {
          agent_id: 7,
          agent_name: "客服助手",
          requests: 2,
          llm_calls: 4,
          prompt_tokens: 80,
          completion_tokens: 30,
          total_tokens: 110,
          last_called_at: "2026-09-10T12:00:00",
        },
        {
          agent_id: null,
          agent_name: "未绑定智能体",
          requests: 0,
          llm_calls: 1,
          prompt_tokens: 20,
          completion_tokens: 10,
          total_tokens: 30,
          last_called_at: "2026-09-11T09:00:00",
        },
      ],
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
    // 明细要保序透传：后端已按总 token 降序，前端不再重排
    expect(result.agents.map((a) => a.agent_name)).toEqual(["客服助手", "未绑定智能体"]);
    expect(result.agents[1].agent_id).toBeNull();
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
        agents: [],
      },
    });

    const result = await getUsageOverview({ start: "2026-01-01", end: "2026-01-31" });

    expect(result.totals.total_tokens).toBe(0);
  });
});
