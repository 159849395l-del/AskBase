/** 管理员：智能体卡片列表 */

import React, { useEffect, useState } from "react";
import { Card, Row, Col, Button, Empty, Spin, Dropdown, Modal, message, theme, Tag } from "antd";
import { PlusOutlined, EllipsisOutlined, EditOutlined, DeleteOutlined, RobotOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { listAgents, deleteAgent } from "../api/agent";
import type { AgentItem } from "../types/agent";

const AgentListPage: React.FC = () => {
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setAgents(await listAgents());
    } catch {
      message.error("加载智能体失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleDelete = (agent: AgentItem) => {
    Modal.confirm({
      title: `确认删除智能体「${agent.name}」？`,
      content: "已存在的会话不会被删除，但将失去该智能体的专属设定。",
      okType: "danger",
      okText: "删除",
      cancelText: "取消",
      onOk: async () => {
        try {
          await deleteAgent(agent.id);
          message.success("已删除");
          load();
        } catch {
          message.error("删除失败");
        }
      },
    });
  };

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center" }}>
        <Spin tip="加载中..." />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h2 style={{ margin: 0 }}>智能体管理</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/admin/agents/new")}>
          新建智能体
        </Button>
      </div>

      {agents.length === 0 ? (
        <Empty description="还没有智能体，点击右上角创建一个吧" style={{ marginTop: 80 }} />
      ) : (
        <Row gutter={[16, 16]}>
          {agents.map((agent) => (
            <Col xs={24} sm={12} md={8} lg={6} key={agent.id}>
              <Card
                hoverable
                style={{
                  borderRadius: 12,
                  border: `1px solid ${themeToken.colorBorderSecondary}`,
                }}
                onClick={() => navigate(`/admin/agents/${agent.id}/edit`)}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 10,
                      background: themeToken.colorPrimaryBg,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 22,
                      flexShrink: 0,
                    }}
                  >
                    {agent.icon || <RobotOutlined />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontWeight: 500, fontSize: 15, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {agent.name}
                      </span>
                      {!agent.is_active && <Tag color="default">停用</Tag>}
                      {agent.is_hidden && <Tag color="orange">用户隐藏</Tag>}
                    </div>
                    <div
                      style={{
                        color: themeToken.colorTextSecondary,
                        fontSize: 12,
                        marginTop: 4,
                        height: 34,
                        overflow: "hidden",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                      }}
                    >
                      {agent.description || "暂无简介"}
                    </div>
                  </div>
                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: "edit",
                          icon: <EditOutlined />,
                          label: "编辑",
                          onClick: ({ domEvent }) => {
                            domEvent.stopPropagation();
                            navigate(`/admin/agents/${agent.id}/edit`);
                          },
                        },
                        {
                          key: "delete",
                          icon: <DeleteOutlined />,
                          label: "删除",
                          danger: true,
                          onClick: ({ domEvent }) => {
                            domEvent.stopPropagation();
                            handleDelete(agent);
                          },
                        },
                      ],
                    }}
                    trigger={["click"]}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<EllipsisOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Dropdown>
                </div>
                <div style={{ marginTop: 10, color: themeToken.colorTextTertiary, fontSize: 12 }}>
                  关联知识库 {agent.kb_ids?.length ?? 0} 个
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
};

export default AgentListPage;
