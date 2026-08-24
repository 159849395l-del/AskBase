/** 爬虫管理 API 调用 */

import apiClient from "./client";
import type {
  CrawlTask,
  TaskListResponse,
  TaskCreateRequest,
  CrawlResult,
  ResultListResponse,
  CrawlSchedule,
  ScheduleRequest,
} from "../types/crawler";

// ===== 任务管理 =====

export async function listTasks(
  page = 0,
  size = 20,
  status?: string,
  keyword?: string
): Promise<TaskListResponse> {
  const resp = await apiClient.get<TaskListResponse>("/crawler/tasks", {
    params: { page, size, status, keyword },
  });
  return resp.data;
}

export async function createTask(body: TaskCreateRequest): Promise<CrawlTask> {
  const resp = await apiClient.post<CrawlTask>("/crawler/tasks", body);
  return resp.data;
}

export async function getTask(taskId: number): Promise<CrawlTask> {
  const resp = await apiClient.get<CrawlTask>(`/crawler/tasks/${taskId}`);
  return resp.data;
}

export async function deleteTask(taskId: number): Promise<void> {
  await apiClient.delete(`/crawler/tasks/${taskId}`);
}

export async function submitTask(taskId: number): Promise<{ message: string; taskId: number }> {
  const resp = await apiClient.post(`/crawler/tasks/${taskId}/submit`);
  return resp.data;
}

export async function restartTask(taskId: number): Promise<CrawlTask> {
  const resp = await apiClient.post<CrawlTask>(`/crawler/tasks/${taskId}/restart`);
  return resp.data;
}

export async function stopTask(taskId: number): Promise<CrawlTask> {
  const resp = await apiClient.post<CrawlTask>(`/crawler/tasks/${taskId}/stop`);
  return resp.data;
}

// ===== 结果管理 =====

export async function listResults(
  taskId: number,
  page = 0,
  size = 20,
  status?: string,
  keyword?: string
): Promise<ResultListResponse> {
  const resp = await apiClient.get<ResultListResponse>(`/crawler/tasks/${taskId}/results`, {
    params: { page, size, status, keyword },
  });
  return resp.data;
}

export async function getResultDetail(taskId: number, resultId: number): Promise<CrawlResult> {
  const resp = await apiClient.get<CrawlResult>(`/crawler/tasks/${taskId}/results/${resultId}`);
  return resp.data;
}

export async function exportResults(taskId: number, format: "csv" | "json" = "csv"): Promise<Blob> {
  const resp = await apiClient.get(`/crawler/tasks/${taskId}/export`, {
    params: { format },
    responseType: "blob",
  });
  return resp.data;
}

// ===== 定时爬取 =====

export async function getSchedule(taskId: number): Promise<CrawlSchedule | null> {
  const resp = await apiClient.get<CrawlSchedule | null>(`/crawler/schedules/${taskId}`);
  return resp.data;
}

export async function saveSchedule(taskId: number, body: ScheduleRequest): Promise<CrawlSchedule> {
  const resp = await apiClient.put<CrawlSchedule>(`/crawler/schedules/${taskId}`, body);
  return resp.data;
}

export async function deleteSchedule(taskId: number): Promise<void> {
  await apiClient.delete(`/crawler/schedules/${taskId}`);
}

// ===== SSE 事件推送 =====

export function connectTaskSSE(
  taskId: number,
  onMessage: (event: string, data: any) => void,
  onError?: (err: Event) => void
): EventSource {
  const token = localStorage.getItem("access_token");
  const url = `/api/crawler/tasks/${taskId}/events?token=${token}`;
  const es = new EventSource(url);

  es.addEventListener("TASK_STATUS", (e) => onMessage("TASK_STATUS", JSON.parse(e.data)));
  es.addEventListener("TASK_ERROR", (e) => onMessage("TASK_ERROR", JSON.parse(e.data)));
  es.addEventListener("AGENT_LOG", (e) => onMessage("AGENT_LOG", JSON.parse(e.data)));
  es.addEventListener("URL_PROGRESS", (e) => onMessage("URL_PROGRESS", JSON.parse(e.data)));
  es.addEventListener("STAGE_PROGRESS", (e) => onMessage("STAGE_PROGRESS", JSON.parse(e.data)));
  es.addEventListener("RESULT_NEW", (e) => onMessage("RESULT_NEW", JSON.parse(e.data)));

  es.onerror = (err) => {
    if (onError) onError(err);
  };

  return es;
}
