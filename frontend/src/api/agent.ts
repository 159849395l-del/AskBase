/** 智能体 API 调用 */

import apiClient from "./client";
import type { AgentItem, AgentDetail, AgentPayload } from "../types/agent";

export async function listAgents(): Promise<AgentItem[]> {
  const resp = await apiClient.get<AgentItem[]>("/agents");
  return resp.data;
}

export async function getAgent(id: number): Promise<AgentDetail> {
  const resp = await apiClient.get<AgentDetail>(`/agents/${id}`);
  return resp.data;
}

export async function createAgent(payload: AgentPayload): Promise<AgentDetail> {
  const resp = await apiClient.post<AgentDetail>("/agents", payload);
  return resp.data;
}

export async function updateAgent(id: number, payload: Partial<AgentPayload>): Promise<AgentDetail> {
  const resp = await apiClient.put<AgentDetail>(`/agents/${id}`, payload);
  return resp.data;
}

export async function deleteAgent(id: number): Promise<void> {
  await apiClient.delete(`/agents/${id}`);
}

/**
 * 获取（或创建）当前用户对该智能体的会话——每个用户×智能体只保持一个会话。
 * 返回会话对象（含 id），前端直接进入。
 */
export async function getOrCreateAgentConversation(
  agentId: number
): Promise<{ id: number; title: string; agent_id: number }> {
  const resp = await apiClient.post(`/agents/${agentId}/conversation`);
  return resp.data;
}

/**
 * 测试智能体配置（SSE 流式，不落库）。
 * 调用方传入当前草稿的 system_prompt / kb_doc_ids，用于编辑页右侧实时预览。
 */
export function testAgentStream(
  payload: { question: string; system_prompt?: string; kb_doc_ids?: number[]; history?: [string, string][] },
  onToken: (t: string) => void,
  onDone: () => void,
  onError: (msg: string) => void
): void {
  const token = localStorage.getItem("access_token") || "";
  fetch("/api/agents/test", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  })
    .then(async (resp) => {
      if (!resp.ok || !resp.body) {
        onError(`请求失败 (${resp.status})`);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() || "";
        for (const line of lines) {
          const t = line.trim();
          if (!t.startsWith("data: ")) continue;
          try {
            const d = JSON.parse(t.slice(6));
            if (d.token) onToken(d.token);
            if (d.message) onToken(d.message); // no_results
            if (d.error) onError(d.error);
          } catch {
            /* ignore */
          }
        }
      }
      onDone();
    })
    .catch((e) => onError(String(e)));
}
