/** 管理员：智能体编辑页（左编辑 + 右预览） */

import React, { useEffect, useRef, useState } from "react";
import {
  Form,
  Input,
  Button,
  Select,
  Switch,
  InputNumber,
  message,
  Spin,
  theme,
  Typography,
  Popconfirm,
} from "antd";
import { SaveOutlined, RollbackOutlined, SendOutlined } from "@ant-design/icons";
import { useParams, useNavigate } from "react-router-dom";
import { getAgent, createAgent, updateAgent, testAgentStream } from "../api/agent";
import { listKnowledgeBases } from "../api/knowledgeBases";
import { listModels } from "../api/models";
import { listSkills } from "../api/skills";
import { listMCPServers, listMCPTools } from "../api/mcpServers";
import type { LLMModelItem } from "../types/llmModel";
import type { SkillItem } from "../types/skill";
import type { MCPServerItem, MCPToolItem } from "../types/mcpServer";
import type { AgentToolRef } from "../types/agent";

const { TextArea } = Input;
const { Text } = Typography;

/** 工具选择框的 value 编码：skill:<id> 或 mcp:<server_id>:<tool_name> */
function encodeTool(t: AgentToolRef): string | null {
  if (t.tool_type === "skill" && t.tool_ref_id) return `skill:${t.tool_ref_id}`;
  if (t.tool_type === "mcp_tool" && t.tool_ref) return `mcp:${t.tool_ref}`;
  return null;
}

function decodeTool(v: string): AgentToolRef | null {
  if (v.startsWith("skill:")) {
    return { tool_type: "skill", tool_ref_id: Number(v.slice(6)), enabled: true };
  }
  if (v.startsWith("mcp:")) {
    return { tool_type: "mcp_tool", tool_ref: v.slice(4), enabled: true };
  }
  return null;
}

interface AgentFormValues {
  name: string;
  description: string;
  icon: string;
  welcome_message: string;
  system_prompt: string;
  is_active: boolean;
  is_hidden: boolean;
  sort_order: number;
  kb_ids: number[];
  model_id?: number | null;
  tool_keys?: string[];
}

interface PreviewMsg {
  role: "user" | "assistant";
  content: string;
}

const AgentEditPage: React.FC = () => {
  const { id } = useParams<{ id?: string }>();
  const isNew = !id;
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();
  const [form] = Form.useForm<AgentFormValues>();
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [kbOptions, setKbOptions] = useState<{ label: string; value: number }[]>([]);
  const [iconValue, setIconValue] = useState("🤖");
  const [modelOptions, setModelOptions] = useState<
    { label: string; value: number }[]
  >([]);
  const [toolOptions, setToolOptions] = useState<
    { label: string; value: string; }[]
  >([]);

  // 预览聊天状态
  const [previewMsgs, setPreviewMsgs] = useState<PreviewMsg[]>([]);
  const [previewInput, setPreviewInput] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 知识库选项（挂载粒度=知识库，而非文档）
    listKnowledgeBases()
      .then((kbs) =>
        setKbOptions(
          kbs.map((kb) => ({
            label: `${kb.name}${kb.type === "database" ? "（数据库型）" : ""}`,
            value: kb.id,
          }))
        )
      )
      .catch(() => {});

    // 模型选项（只列启用中的）
    listModels()
      .then((ms: LLMModelItem[]) =>
        setModelOptions(
          ms
            .filter((m) => m.is_active)
            .map((m) => ({
              label: `${m.name}${m.is_default ? "（默认）" : ""}`,
              value: m.id,
            }))
        )
      )
      .catch(() => {});

    // 工具选项：内部 Skill + 各 MCP 服务下已发现的工具
    (async () => {
      try {
        const opts: { label: string; value: string }[] = [];
        const skills: SkillItem[] = await listSkills();
        skills
          .filter((s) => s.is_active)
          .forEach((s) =>
            opts.push({
              label: `${s.icon || "🔧"} ${s.title || s.name}`,
              value: `skill:${s.id}`,
            })
          );
        const servers: MCPServerItem[] = await listMCPServers();
        for (const sv of servers.filter((s) => s.is_active && s.tool_count > 0)) {
          const tools: MCPToolItem[] = await listMCPTools(sv.id);
          tools.forEach((t) =>
            opts.push({
              label: `${sv.name} / ${t.name}`,
              value: `mcp:${sv.id}:${t.name}`,
            })
          );
        }
        setToolOptions(opts);
      } catch {
        /* 工具模块异常不影响智能体编辑 */
      }
    })();

    if (!isNew) {
      getAgent(Number(id))
        .then((agent) => {
          form.setFieldsValue({
            name: agent.name,
            description: agent.description,
            icon: agent.icon,
            welcome_message: agent.welcome_message,
            system_prompt: agent.system_prompt,
            is_active: agent.is_active,
            is_hidden: agent.is_hidden,
            sort_order: agent.sort_order,
            kb_ids: agent.kb_ids,
            model_id: agent.model_id ?? undefined,
            tool_keys: (agent.tools || [])
              .map(encodeTool)
              .filter((x): x is string => !!x),
          });
          setIconValue(agent.icon || "🤖");
          setLoading(false);
        })
        .catch(() => {
          message.error("加载智能体失败");
          navigate("/admin/agents");
        });
    }
  }, [id]);

  useEffect(() => {
    previewEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [previewMsgs]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const { tool_keys, ...rest } = values;
      const payload = {
        ...rest,
        tools: (tool_keys || [])
          .map(decodeTool)
          .filter((t): t is AgentToolRef => !!t),
      };
      setSaving(true);
      if (isNew) {
        const created = await createAgent(payload);
        message.success("创建成功");
        navigate(`/admin/agents/${created.id}/edit`, { replace: true });
      } else {
        await updateAgent(Number(id), payload);
        message.success("保存成功");
      }
    } catch (e: any) {
      if (e?.errorFields) return; // 表单校验错误
      message.error("保存失败：" + (e?.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  // 预览：发送测试消息（使用当前表单草稿配置）
  const handlePreviewSend = async () => {
    const q = previewInput.trim();
    if (!q || previewLoading) return;

    let draft: AgentFormValues;
    try {
      draft = await form.validateFields();
    } catch {
      draft = form.getFieldsValue();
    }

    const history: [string, string][] = previewMsgs.map((m) =>
      m.role === "user" ? ["human", m.content] : ["ai", m.content]
    );

    setPreviewMsgs((prev) => [...prev, { role: "user", content: q }]);
    setPreviewInput("");
    setPreviewLoading(true);
    const assistantMsg: PreviewMsg = { role: "assistant", content: "" };
    setPreviewMsgs((prev) => [...prev, assistantMsg]);

    testAgentStream(
      {
        question: q,
        system_prompt: draft.system_prompt,
        kb_ids: draft.kb_ids || [],
        history,
        model_id: draft.model_id ?? null,
        tools: (draft.tool_keys || [])
          .map(decodeTool)
          .filter((t): t is AgentToolRef => !!t),
      },
      (token) => {
        setPreviewMsgs((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant") {
            copy[copy.length - 1] = { ...last, content: last.content + token };
          }
          return copy;
        });
      },
      () => setPreviewLoading(false),
      (err) => {
        setPreviewMsgs((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant" && !last.content) {
            copy[copy.length - 1] = { ...last, content: `[出错] ${err}` };
          }
          return copy;
        });
        setPreviewLoading(false);
      }
    );
  };

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="加载中..." />
      </div>
    );
  }

  const ICON_OPTIONS = ["🤖", "🎓", "📚", "💼", "🛒", "📊", "🔧", "💡", "🏥", "⚖️", "✈️"];

  return (
    <div style={{ padding: 24, height: "100%", maxWidth: 1280, margin: "0 auto" }}>
      {/* 顶部操作条 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>{isNew ? "新建智能体" : "编辑智能体"}</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <Button icon={<RollbackOutlined />} onClick={() => navigate("/admin/agents")}>
            返回
          </Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
            保存
          </Button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, height: "calc(100vh - 140px)" }}>
        {/* 左侧：编辑表单 */}
        <div
          style={{
            flex: "1 1 55%",
            overflow: "auto",
            background: themeToken.colorBgContainer,
            borderRadius: 12,
            border: `1px solid ${themeToken.colorBorderSecondary}`,
            padding: 20,
          }}
        >
          <Form form={form} layout="vertical" initialValues={{
            icon: "🤖",
            description: "",
            welcome_message: "您好，我是您的专属AI助手，请问有什么可以帮助您呢？",
            system_prompt: "",
            is_active: true,
            is_hidden: false,
            sort_order: 0,
            kb_ids: [],
            model_id: undefined,
            tool_keys: [],
          }}>
            <Form.Item name="name" label="名称" rules={[{ required: true, message: "请输入名称" }]}>
              <Input placeholder="如：招生问答助手" maxLength={100} />
            </Form.Item>

            <Form.Item name="description" label="简介">
              <Input placeholder="一句话描述该智能体的用途" maxLength={500} />
            </Form.Item>

            <Form.Item label="图标">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {ICON_OPTIONS.map((ic) => (
                  <div
                    key={ic}
                    onClick={() => {
                      setIconValue(ic);
                      form.setFieldValue("icon", ic);
                    }}
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: 8,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 20,
                      cursor: "pointer",
                      border:
                        iconValue === ic
                          ? `2px solid ${themeToken.colorPrimary}`
                          : `1px solid ${themeToken.colorBorderSecondary}`,
                      background: iconValue === ic ? themeToken.colorPrimaryBg : "transparent",
                    }}
                  >
                    {ic}
                  </div>
                ))}
              </div>
            </Form.Item>
            <Form.Item name="icon" hidden>
              <Input />
            </Form.Item>

            <Form.Item name="welcome_message" label="欢迎语" rules={[{ required: true, message: "请输入欢迎语" }]}>
              <TextArea rows={2} placeholder="用户进入对话时看到的第一句话" maxLength={500} />
            </Form.Item>

            <Form.Item
              name="system_prompt"
              label="提示词（智能体设定）"
              extra="设定智能体的角色与回答风格；留空则使用系统默认。检索到的知识库内容会自动附在提示词后"
            >
              <TextArea rows={6} placeholder="如：你是西华师范大学招生问答助手，用亲切的口吻准确回答招生问题…" />
            </Form.Item>

            <Form.Item
              name="kb_ids"
              label="关联知识库"
              extra="勾选后该智能体只从这些知识库中检索作答；数据库型知识库最多选 1 个（多个会导致 SQL 不知道查哪个库/表）"
            >
              <Select
                mode="multiple"
                placeholder="选择知识库（可多选，数据库型最多 1 个）"
                options={kbOptions}
                allowClear
              />
            </Form.Item>

            <Form.Item
              name="model_id"
              label="使用模型"
              extra="不选则使用大模型库中的默认模型；未配置任何模型时回退 .env 配置"
            >
              <Select
                placeholder="系统默认模型"
                options={modelOptions}
                allowClear
              />
            </Form.Item>

            <Form.Item
              name="tool_keys"
              label="启用工具"
              extra="勾选后模型可在需要时调用这些工具；模型必须支持工具调用才会生效"
            >
              <Select
                mode="multiple"
                placeholder="选择内部 Skill / MCP 工具（可多选）"
                options={toolOptions}
                allowClear
              />
            </Form.Item>

            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <Form.Item name="sort_order" label="排序" style={{ width: 120 }}>
                <InputNumber min={0} style={{ width: "100%" }} />
              </Form.Item>
              <Form.Item name="is_active" label="启用" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item
                name="is_hidden"
                label="对用户隐藏"
                valuePropName="checked"
                extra="开启后用户端不可见、不可进入（管理员仍可管理）"
              >
                <Switch />
              </Form.Item>
            </div>
          </Form>
        </div>

        {/* 右侧：实时预览 */}
        <div
          style={{
            flex: "1 1 45%",
            display: "flex",
            flexDirection: "column",
            background: themeToken.colorBgContainer,
            borderRadius: 12,
            border: `1px solid ${themeToken.colorBorderSecondary}`,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "12px 16px",
              borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
              fontWeight: 500,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <span style={{ fontSize: 20 }}>{iconValue}</span>
            {form.getFieldValue("name") || "智能体预览"}
            <Text type="secondary" style={{ marginLeft: "auto", fontSize: 12 }}>
              保存前可实时测试
            </Text>
          </div>

          {/* 消息区 */}
          <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
            {previewMsgs.length === 0 ? (
              <div style={{ textAlign: "center", marginTop: 60, color: themeToken.colorTextTertiary }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>{iconValue}</div>
                <div>{form.getFieldValue("welcome_message") || "在下方输入问题测试智能体效果"}</div>
              </div>
            ) : (
              previewMsgs.map((m, i) => (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      maxWidth: "80%",
                      padding: "8px 12px",
                      borderRadius: 10,
                      whiteSpace: "pre-wrap",
                      fontSize: 13,
                      lineHeight: 1.6,
                      background:
                        m.role === "user" ? themeToken.colorPrimary : themeToken.colorBgLayout,
                      color: m.role === "user" ? "#fff" : themeToken.colorText,
                    }}
                  >
                    {m.content}
                  </div>
                </div>
              ))
            )}
            <div ref={previewEndRef} />
          </div>

          {/* 输入区 */}
          <div style={{ padding: 12, borderTop: `1px solid ${themeToken.colorBorderSecondary}` }}>
            <div style={{ display: "flex", gap: 8 }}>
              <Input
                placeholder="输入测试问题…"
                value={previewInput}
                onChange={(e) => setPreviewInput(e.target.value)}
                onPressEnter={handlePreviewSend}
                disabled={previewLoading}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handlePreviewSend}
                loading={previewLoading}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentEditPage;
