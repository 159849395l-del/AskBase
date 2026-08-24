/** 爬虫模块类型定义 */

export interface CrawlTask {
  id: number;
  taskNo: string;
  title: string;
  description: string;
  seedUrls: string[];
  maxPages: number;
  maxDepth: number;
  sameDomainOnly: boolean;
  status: TaskStatusEnum;
  schema: Record<string, any> | null;
  plan: Record<string, any> | null;
  stats: Record<string, any>;
  errorMessage: string | null;
  startedAt: string | null;
  finishedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export type TaskStatusEnum =
  | "PENDING"
  | "PLANNING"
  | "DISCOVERING"
  | "CRAWLING"
  | "EXTRACTING"
  | "VERIFYING"
  | "AGGREGATING"
  | "COMPLETED"
  | "PARTIAL"
  | "FAILED"
  | "CANCELLED";

export const TASK_STATUS_LABELS: Record<TaskStatusEnum, string> = {
  PENDING: "待处理",
  PLANNING: "规划中",
  DISCOVERING: "发现中",
  CRAWLING: "爬取中",
  EXTRACTING: "提取中",
  VERIFYING: "验证中",
  AGGREGATING: "聚合中",
  COMPLETED: "已完成",
  PARTIAL: "部分完成",
  FAILED: "失败",
  CANCELLED: "已取消",
};

export const TASK_STATUS_COLORS: Record<TaskStatusEnum, string> = {
  PENDING: "default",
  PLANNING: "processing",
  DISCOVERING: "processing",
  CRAWLING: "processing",
  EXTRACTING: "processing",
  VERIFYING: "processing",
  AGGREGATING: "processing",
  COMPLETED: "success",
  PARTIAL: "warning",
  FAILED: "error",
  CANCELLED: "default",
};

/** 提取结果状态中文映射（与任务状态的中文展示保持一致） */
export const RESULT_STATUS_LABELS: Record<string, string> = {
  VALID: "有效",
  INVALID: "无效",
  DUPLICATE: "重复",
};

export interface TaskListResponse {
  items: CrawlTask[];
  total: number;
  page: number;
  size: number;
}

export interface CrawlResult {
  id: number;
  taskId: number;
  url: string;
  pageId: number | null;
  data: Record<string, any>;
  recordHash: string;
  status: string;
  sourceUrl: string | null;
  extractedAt: string | null;
  createdAt: string;
  pageText?: string | null;
}

export interface ResultListResponse {
  items: CrawlResult[];
  total: number;
  page: number;
  size: number;
}

export interface CrawlSchedule {
  id: number;
  taskId: number;
  intervalDays: number;
  runTime: string;
  enabled: boolean;
  lastRunAt: string | null;
  lastStatus: string;
  lastDetail: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SSEMessage {
  event: string;
  data: any;
}

export interface TaskCreateRequest {
  title?: string;
  description: string;
  seed_urls: string[];
  max_pages: number;
  max_depth: number;
  same_domain_only: boolean;
}

export interface ScheduleRequest {
  interval_days: number;
  run_time: string;
  enabled: boolean;
}
