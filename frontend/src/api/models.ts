/** 大模型库 API 调用 */

import apiClient from "./client";
import type {
  LLMModelItem,
  LLMModelForm,
  ProviderOption,
  ModelTestResponse,
} from "../types/llmModel";

export async function listProviders(): Promise<ProviderOption[]> {
  const resp = await apiClient.get<ProviderOption[]>("/models/providers");
  return resp.data;
}

export async function listModels(): Promise<LLMModelItem[]> {
  const resp = await apiClient.get<LLMModelItem[]>("/models");
  return resp.data;
}

export async function createModel(form: LLMModelForm): Promise<LLMModelItem> {
  const resp = await apiClient.post<LLMModelItem>("/models", form);
  return resp.data;
}

export async function updateModel(
  id: number,
  form: Partial<LLMModelForm>
): Promise<LLMModelItem> {
  const resp = await apiClient.put<LLMModelItem>(`/models/${id}`, form);
  return resp.data;
}

export async function deleteModel(id: number): Promise<void> {
  await apiClient.delete(`/models/${id}`);
}

export async function testModel(id: number): Promise<ModelTestResponse> {
  const resp = await apiClient.post<ModelTestResponse>(`/models/${id}/test`);
  return resp.data;
}

export async function setDefaultModel(id: number): Promise<LLMModelItem> {
  const resp = await apiClient.post<LLMModelItem>(`/models/${id}/set-default`);
  return resp.data;
}
