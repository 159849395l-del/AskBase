/** 用量统计 API 调用 */

import apiClient from "./client";
import type { UsageOverview } from "../types/usage";

export interface UsageRangeParams {
  /** 起始日期（含），格式 YYYY-MM-DD */
  start: string;
  /** 结束日期（含），格式 YYYY-MM-DD */
  end: string;
}

/** 汇总时间范围内的真实用量（仅管理员可访问） */
export async function getUsageOverview(params: UsageRangeParams): Promise<UsageOverview> {
  const resp = await apiClient.get<UsageOverview>("/admin/usage/overview", { params });
  return resp.data;
}
