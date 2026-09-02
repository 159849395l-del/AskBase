/** 内部 Skill（AI 智能工具）API 调用 */

import apiClient from "./client";
import type { SkillItem, SkillForm, SkillTestResponse } from "../types/skill";

export async function listSkills(): Promise<SkillItem[]> {
  const resp = await apiClient.get<SkillItem[]>("/skills");
  return resp.data;
}

export async function createSkill(form: SkillForm): Promise<SkillItem> {
  const resp = await apiClient.post<SkillItem>("/skills", form);
  return resp.data;
}

export async function updateSkill(
  id: number,
  form: Partial<SkillForm>
): Promise<SkillItem> {
  const resp = await apiClient.put<SkillItem>(`/skills/${id}`, form);
  return resp.data;
}

export async function deleteSkill(id: number): Promise<void> {
  await apiClient.delete(`/skills/${id}`);
}

export async function testSkill(
  id: number,
  args: Record<string, unknown>
): Promise<SkillTestResponse> {
  const resp = await apiClient.post<SkillTestResponse>(`/skills/${id}/test`, {
    arguments: args,
  });
  return resp.data;
}

export async function seedBuiltinSkills(): Promise<{ message: string }> {
  const resp = await apiClient.post<{ message: string }>("/skills/seed-builtin");
  return resp.data;
}
