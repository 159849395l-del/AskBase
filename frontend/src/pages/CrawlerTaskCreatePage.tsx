/** 爬虫任务创建页 */

import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card, Form, Input, InputNumber, Switch, Button, message,
  Typography, Space, Divider,
} from "antd";
import { ArrowLeftOutlined, SaveOutlined } from "@ant-design/icons";
import { createTask } from "../api/crawler";

const { Title } = Typography;
const { TextArea } = Input;

const CrawlerTaskCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: any) => {
    setSubmitting(true);
    try {
      const task = await createTask({
        title: values.title,
        description: values.description,
        seed_urls: values.seedUrls
          ? values.seedUrls.split("\n").map((s: string) => s.trim()).filter(Boolean)
          : [],
        max_pages: values.maxPages || 100,
        max_depth: values.maxDepth || 3,
        same_domain_only: values.sameDomainOnly !== false,
      });
      message.success(`任务 "${task.title}" 创建成功`);
      navigate(`/admin/crawler/tasks/${task.id}`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || "创建失败");
    }
    setSubmitting(false);
  };

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate("/admin/crawler/tasks")}
        >
          返回列表
        </Button>
      </Space>
      <Title level={4}>新建爬虫任务</Title>

      <Card style={{ maxWidth: 720 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            max_pages: 100,
            max_depth: 3,
            same_domain_only: true,
          }}
        >
          <Form.Item
            name="title"
            label="任务标题"
            rules={[{ required: true, message: "请输入任务标题" }]}
          >
            <Input placeholder="为任务起一个名字" />
          </Form.Item>

          <Form.Item
            name="description"
            label="任务描述"
            rules={[{ required: true, message: "请输入任务描述" }]}
          >
            <TextArea rows={3} placeholder="描述这个爬虫任务的目标" />
          </Form.Item>

          <Form.Item
            name="seedUrls"
            label="种子 URL"
            tooltip="每行一个 URL，爬虫将从这些地址开始爬取"
          >
            <TextArea
              rows={5}
              placeholder={"https://example.com\nhttps://example.com/page1"}
            />
          </Form.Item>

          <Divider />

          <Space size={24} wrap>
            <Form.Item name="maxPages" label="最大页数" style={{ width: 120 }}>
              <InputNumber min={1} max={10000} style={{ width: 120 }} />
            </Form.Item>

            <Form.Item name="maxDepth" label="最大深度" style={{ width: 120 }}>
              <InputNumber min={1} max={10} style={{ width: 120 }} />
            </Form.Item>

            <Form.Item
              name="sameDomainOnly"
              label="仅同域名"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </Space>

          <Divider />

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={submitting}
            >
              创建任务
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default CrawlerTaskCreatePage;
