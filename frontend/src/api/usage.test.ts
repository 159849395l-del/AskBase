/** usage API 单元测试 — 请求地址、查询参数与返回值透传 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import apiClient from "./client";
import { getUsageOverview, getUsageTimeseries } from "./usage";

vi.mock("./client", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

const mockedGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

const OVERVIEW_PAYLOAD = {
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

describe("getUsageOverview — 用量总览", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("场景：传入粒度与起止日期 → 原样带上参数并透传返回值", async () => {
    mockedGet.mockResolvedValue({ data: OVERVIEW_PAYLOAD });

    const result = await getUsageOverview({
      granularity: "day",
      start: "2026-09-01",
      end: "2026-09-30",
    });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/overview", {
      params: { granularity: "day", start: "2026-09-01", end: "2026-09-30" },
    });
    expect(result).toEqual(OVERVIEW_PAYLOAD);
    // 两个计数与被排除的估算数都要原样透传，前端才能如实呈现口径
    expect(result.totals.requests).toBe(2);
    expect(result.totals.llm_calls).toBe(5);
    expect(result.excluded.estimated_calls).toBe(1);
    // 明细要保序透传：后端已按总 token 降序，前端不再重排
    expect(result.agents.map((a) => a.agent_name)).toEqual(["客服助手", "未绑定智能体"]);
    expect(result.agents[1].agent_id).toBeNull();
  });

  it("场景：只给粒度不传日期 → 不带起止参数，缺省区间由后端推导", async () => {
    mockedGet.mockResolvedValue({ data: OVERVIEW_PAYLOAD });

    await getUsageOverview({ granularity: "month" });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/overview", {
      params: { granularity: "month" },
    });
  });

  it("场景：限定到某个智能体 → 请求带上 agent_id", async () => {
    mockedGet.mockResolvedValue({ data: OVERVIEW_PAYLOAD });

    await getUsageOverview({ granularity: "day", agent_id: 7 });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/overview", {
      params: { granularity: "day", agent_id: 7 },
    });
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

    const result = await getUsageOverview({ granularity: "day" });

    expect(result.totals.total_tokens).toBe(0);
  });
});

describe("getUsageTimeseries — 用量时间序列", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("场景：指定粒度与区间 → 请求 /admin/usage/timeseries 并原样透传时间桶", async () => {
    const payload = {
      granularity: "month",
      start: "2025-10-01",
      end: "2026-09-11",
      points: [
        {
          bucket: "2026-08",
          requests: 1,
          llm_calls: 2,
          prompt_tokens: 100,
          completion_tokens: 20,
          total_tokens: 120,
        },
        {
          bucket: "2026-09",
          requests: 0,
          llm_calls: 0,
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
      ],
    };
    mockedGet.mockResolvedValue({ data: payload });

    const result = await getUsageTimeseries({
      granularity: "month",
      start: "2025-10-01",
      end: "2026-09-11",
    });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/timeseries", {
      params: { granularity: "month", start: "2025-10-01", end: "2026-09-11" },
    });
    // 补零的桶必须原样保留，前端据此画出连续曲线
    expect(result.points.map((p) => p.bucket)).toEqual(["2026-08", "2026-09"]);
    expect(result.points[1].total_tokens).toBe(0);
  });

  it("场景：限定到某个智能体 → 时间序列请求同样带上 agent_id", async () => {
    mockedGet.mockResolvedValue({
      data: { granularity: "day", start: "2026-09-01", end: "2026-09-30", points: [] },
    });

    await getUsageTimeseries({
      granularity: "day",
      start: "2026-09-01",
      end: "2026-09-30",
      agent_id: 7,
    });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/timeseries", {
      params: {
        granularity: "day",
        start: "2026-09-01",
        end: "2026-09-30",
        agent_id: 7,
      },
    });
  });

  it("场景：只给粒度 → 缺省区间同样由后端推导", async () => {
    mockedGet.mockResolvedValue({
      data: { granularity: "year", start: "2022-01-01", end: "2026-09-11", points: [] },
    });

    await getUsageTimeseries({ granularity: "year" });

    expect(mockedGet).toHaveBeenCalledWith("/admin/usage/timeseries", {
      params: { granularity: "year" },
    });
  });
});
