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

/** 按智能体聚合的一行明细 */
export interface UsageAgentRow {
  /** 无归属的调用为 null，在报表里显示为「未绑定智能体」 */
  agent_id: number | null;
  /** 名称取该智能体最近一次调用留下的快照 */
  agent_name: string;
  requests: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  last_called_at: string | null;
}

/** 用量总览：范围 + 合计 + 排除情况 + 按智能体明细（按总 token 降序） */
export interface UsageOverview {
  start: string;
  end: string;
  totals: UsageTotals;
  excluded: UsageExcluded;
  agents: UsageAgentRow[];
}
