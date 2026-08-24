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
import { listDocuments } from "../api/kb";

const { TextArea } = Input;
const { Text } = Typography;

interface AgentFormValues {
  name: string;
  description: string;
  icon: string;
  welcome_message: string;
  system_prompt: string;
  is_active: boolean;
  is_hidden: boolean;
  sort_order: number;
  kb_doc_ids: number[];
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

  // 预览聊天状态
  const [previewMsgs, setPreviewMsgs] = useState<PreviewMsg[]>([]);
  const [previewInput, setPreviewInput] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const previewEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // 知识库选项（后端 page_size 上限 100）
    listDocuments(1, 100)
      .then((resp) =>
        setKbOptions(
          resp.items.map((d) => ({ label: `${d.filename} (${d.chunk_count}块)`, value: d.id }))
        )
      )
      .catch(() => {});

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
            kb_doc_ids: agent.kb_doc_ids,
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
      setSaving(true);
      if (isNew) {
        const created = await createAgent(values);
        message.success("创建成功");
        navigate(`/admin/agents/${created.id}/edit`, { replace: true });
      } else {
        await updateAgent(Number(id), values);
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
        kb_doc_ids: draft.kb_doc_ids || [],
        history,
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
            kb_doc_ids: [],
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
              name="kb_doc_ids"
              label="关联知识库"
              extra="勾选后该智能体只从这些知识库中检索作答；不选则检索全部知识库"
            >
              <Select
                mode="multiple"
                placeholder="选择知识库（可多选）"
                options={kbOptions}
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
