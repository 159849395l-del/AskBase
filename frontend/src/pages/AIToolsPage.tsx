/**
 * AI 智能工具页面 — 只读展示（仅管理员）
 *
 * 工具统一由系统内置（在 backend/app/skills 中注册实现），不在界面增删改，
 * 避免出现"有壳无执行体"的空工具。MCP 服务由连接器侧统一管理，此处仅展示。
 */

import React, { useEffect, useState, useCallback } from "react";
import {
  Tabs,
  Card,
  Button,
  message,
  Typography,
  Space,
  Tag,
  Spin,
  Empty,
  Tooltip,
} from "antd";
import {
  ReloadOutlined,
  ToolOutlined,
  ApiOutlined,
  DownOutlined,
} from "@ant-design/icons";
import type { SkillItem } from "../types/skill";
import type { MCPServerItem, MCPToolItem } from "../types/mcpServer";
import { listSkills } from "../api/skills";
import { listMCPServers, listMCPTools } from "../api/mcpServers";

const { Title, Text, Paragraph } = Typography;

const AIToolsPage: React.FC = () => {
  const [tab, setTab] = useState<"skills" | "mcp">("skills");

  // ---------- 内部工具（只读） ----------
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [skillLoading, setSkillLoading] = useState(false);

  // ---------- MCP 服务（只读 + 可展开看工具） ----------
  const [servers, setServers] = useState<MCPServerItem[]>([]);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [serverTools, setServerTools] = useState<Record<number, MCPToolItem[]>>({});
  const [loadingTools, setLoadingTools] = useState<number | null>(null);

  const fetchSkills = useCallback(async () => {
    setSkillLoading(true);
    try {
      setSkills(await listSkills());
    } catch {
      message.error("获取工具列表失败");
    }
    setSkillLoading(false);
  }, []);

  const fetchServers = useCallback(async () => {
    setMcpLoading(true);
    try {
      setServers(await listMCPServers());
    } catch {
      message.error("获取 MCP 服务列表失败");
    }
    setMcpLoading(false);
  }, []);

  useEffect(() => {
    fetchSkills();
    fetchServers();
  }, [fetchSkills, fetchServers]);

  const toggleTools = async (serverId: number) => {
    if (serverTools[serverId]) {
      // 已展开则收起
      setServerTools((prev) => {
        const next = { ...prev };
        delete next[serverId];
        return next;
      });
      return;
    }
    setLoadingTools(serverId);
    try {
      const tools = await listMCPTools(serverId);
      setServerTools((prev) => ({ ...prev, [serverId]: tools }));
    } catch {
      message.error("获取该服务工具失败（服务可能未连接）");
    }
    setLoadingTools(null);
  };

  const renderSkillCard = (s: SkillItem) => (
    <Card key={s.id} size="small" style={{ width: 280 }}>
      <Space align="start">
        <span style={{ fontSize: 26 }}>{s.icon || "🔧"}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Text strong>{s.title}</Text>
          <div>
            <Text code style={{ fontSize: 12 }}>
              {s.name}
            </Text>
          </div>
        </div>
      </Space>
      <Paragraph
        type="secondary"
        style={{ fontSize: 12, marginTop: 8, marginBottom: 8, minHeight: 54 }}
        ellipsis={{ rows: 3, tooltip: s.description }}
      >
        {s.description}
      </Paragraph>
      <Space size={4} wrap>
        {s.is_builtin && <Tag color="blue">内置</Tag>}
        <Tag color={s.is_active ? "green" : "default"}>{s.is_active ? "启用" : "停用"}</Tag>
        {s.is_dangerous && <Tag color="red">危险</Tag>}
      </Space>
    </Card>
  );

  const renderServerCard = (sv: MCPServerItem) => {
    const expanded = !!serverTools[sv.id];
    const tools = serverTools[sv.id] || [];
    return (
      <Card key={sv.id} size="small" style={{ marginBottom: 12 }}>
        <Space align="start" style={{ width: "100%" }}>
          <span style={{ fontSize: 20 }}>🔌</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <Space>
              <Text strong>{sv.name}</Text>
              <Tag>{sv.transport}</Tag>
              <Tag color={sv.is_active ? "green" : "default"}>
                {sv.is_active ? "启用" : "停用"}
              </Tag>
              {sv.last_error && <Tag color="red">异常</Tag>}
            </Space>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {sv.description || "无描述"}
              </Text>
            </div>
            {expanded && (
              <div style={{ marginTop: 8 }}>
                {tools.length === 0 ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    未获取到工具（服务未连接或无工具）
                  </Text>
                ) : (
                  <Space size={[4, 4]} wrap>
                    {tools.map((t) => (
                      <Tooltip key={t.name} title={t.description || t.title}>
                        <Tag style={{ cursor: "default" }}>{t.name}</Tag>
                      </Tooltip>
                    ))}
                  </Space>
                )}
              </div>
            )}
          </div>
          <Button
            type="link"
            size="small"
            icon={<DownOutlined rotate={expanded ? 180 : 0} />}
            loading={loadingTools === sv.id}
            onClick={() => toggleTools(sv.id)}
          >
            {expanded ? "收起" : "工具"}
          </Button>
        </Space>
      </Card>
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={4} style={{ marginBottom: 4 }}>
        AI 智能工具
      </Title>
      <Text type="secondary" style={{ fontSize: 13 }}>
        工具由系统内置提供，不在页面中增删改；新增能力请联系开发者在代码中注册。
      </Text>

      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as "skills" | "mcp")}
        items={[
          {
            key: "skills",
            label: (
              <span>
                <ToolOutlined /> 内部工具
              </span>
            ),
            children: (
              <Spin spinning={skillLoading}>
                {skills.length === 0 ? (
                  <Empty description="暂无内置工具" />
                ) : (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 16,
                    }}
                  >
                    {skills.map(renderSkillCard)}
                  </div>
                )}
              </Spin>
            ),
          },
          {
            key: "mcp",
            label: (
              <span>
                <ApiOutlined /> MCP 服务
              </span>
            ),
            children: (
              <Spin spinning={mcpLoading}>
                {servers.length === 0 ? (
                  <Empty description="暂无 MCP 服务" />
                ) : (
                  <div style={{ maxWidth: 720 }}>{servers.map(renderServerCard)}</div>
                )}
              </Spin>
            ),
          },
        ]}
        tabBarExtraContent={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              fetchSkills();
              fetchServers();
            }}
          >
            刷新
          </Button>
        }
      />
    </div>
  );
};

export default AIToolsPage;
