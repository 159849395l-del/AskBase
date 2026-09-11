/** 用量统计 API 调用 */

import apiClient from "./client";
import type { UsageGranularity, UsageOverview, UsageTimeseries } from "../types/usage";

export interface UsageQueryParams {
  /** 时间粒度；不传起止日期时，缺省区间按它推导（日近 30 天 / 月近 12 个月 / 年近 5 年） */
  granularity: UsageGranularity;
  /** 起始日期（含），格式 YYYY-MM-DD；不传则由后端按粒度推导 */
  start?: string;
  /** 结束日期（含），格式 YYYY-MM-DD；不传则为今天 */
  end?: string;
  /** 限定到某个智能体；不传为全部（整页作用域下钻） */
  agent_id?: number;
}

/** 汇总范围内的真实用量 + 按智能体明细（仅管理员可访问） */
export async function getUsageOverview(params: UsageQueryParams): Promise<UsageOverview> {
  const resp = await apiClient.get<UsageOverview>("/admin/usage/overview", { params });
  return resp.data;
}

/** 按日/月/年取用量时间序列，没有数据的时间桶为 0（仅管理员可访问） */
export async function getUsageTimeseries(
  params: UsageQueryParams
): Promise<UsageTimeseries> {
  const resp = await apiClient.get<UsageTimeseries>("/admin/usage/timeseries", { params });
  return resp.data;
}
