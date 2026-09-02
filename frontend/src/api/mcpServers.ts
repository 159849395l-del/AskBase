/** MCP 服务 API 调用 */

import apiClient from "./client";
import type {
  MCPServerItem,
  MCPServerDetail,
  MCPServerForm,
  MCPToolItem,
  DiscoverResponse,
  MCPToolCallResponse,
} from "../types/mcpServer";

export async function listMCPServers(): Promise<MCPServerItem[]> {
  const resp = await apiClient.get<MCPServerItem[]>("/mcp-servers");
  return resp.data;
}

export async function getMCPServer(id: number): Promise<MCPServerDetail> {
  const resp = await apiClient.get<MCPServerDetail>(`/mcp-servers/${id}`);
  return resp.data;
}

export async function createMCPServer(
  form: MCPServerForm
): Promise<MCPServerDetail> {
  const resp = await apiClient.post<MCPServerDetail>("/mcp-servers", form);
  return resp.data;
}

export async function updateMCPServer(
  id: number,
  form: Partial<MCPServerForm>
): Promise<MCPServerDetail> {
  const resp = await apiClient.put<MCPServerDetail>(`/mcp-servers/${id}`, form);
  return resp.data;
}

export async function deleteMCPServer(id: number): Promise<void> {
  await apiClient.delete(`/mcp-servers/${id}`);
}

/** 连接服务并拉取工具列表（tools/list） */
export async function discoverMCPTools(id: number): Promise<DiscoverResponse> {
  const resp = await apiClient.post<DiscoverResponse>(
    `/mcp-servers/${id}/discover`
  );
  return resp.data;
}

/** 读取缓存的工具列表（不连接服务） */
export async function listMCPTools(id: number): Promise<MCPToolItem[]> {
  const resp = await apiClient.get<MCPToolItem[]>(`/mcp-servers/${id}/tools`);
  return resp.data;
}

export async function callMCPTool(
  id: number,
  toolName: string,
  args: Record<string, unknown>
): Promise<MCPToolCallResponse> {
  const resp = await apiClient.post<MCPToolCallResponse>(
    `/mcp-servers/${id}/tools/${encodeURIComponent(toolName)}/call`,
    { arguments: args }
  );
  return resp.data;
}
