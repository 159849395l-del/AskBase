/** 用量统计相关类型 */

/** 一段时间范围内的真实用量合计（不含估算行与失败行） */
export interface UsageTotals {
  /** 问答次数：一次提问算一次（只数主回答调用） */
  requests: number;
  /** 模型调用次数：含改写、压缩、Text-to-SQL、工具轮在内的全部调用 */
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/** 被排除出统计的调用数，仅用于提示数据是否完整，不参与任何合计 */
export interface UsageExcluded {
  estimated_calls: number;
}

/** 用量总览：范围 + 合计 + 排除情况 */
export interface UsageOverview {
  start: string;
  end: string;
  totals: UsageTotals;
  excluded: UsageExcluded;
}
