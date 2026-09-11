/** 用量统计相关类型 */

/** 一段时间范围内的真实用量合计（不含估算行与失败行） */
export interface UsageTotals {
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/** 用量总览：范围 + 合计 */
export interface UsageOverview {
  start: string;
  end: string;
  totals: UsageTotals;
}
