/** SourceCitations 组件测试 — 网页来源要可点击，编号要与位置一致 */

import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SourceCitations from "./SourceCitations";
import type { SourceItem } from "../../types/chat";

// antd 组件在 jsdom 下需要 matchMedia 模拟
beforeEach(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  cleanup();
});

const DOC_SOURCE: SourceItem = {
  kind: "doc",
  filename: "policy.md",
  chunk_text: "春节放假 9 天",
  similarity_score: 0.9,
  chunk_index: 0,
  score_type: "vector",
};

const WEB_SOURCE: SourceItem = {
  kind: "web",
  filename: "国务院通知",
  title: "国务院办公厅关于2026年部分节假日安排的通知",
  url: "https://www.gov.cn/zhengce/content_7047091.htm",
  snippet: "春节 2 月 15 日至 2 月 23 日放假调休。",
  published: "2025-11-04T00:00:00.000Z",
};

/** 展开指定来源的折叠面板，children 才会真正挂载 */
function expandSource(index: number) {
  const headers = document.querySelectorAll(".ant-collapse-header");
  fireEvent.click(headers[index]);
}

describe("SourceCitations — 网页来源", () => {
  it("渲染可点击的外链与标题", () => {
    render(<SourceCitations sources={[WEB_SOURCE]} />);

    expect(screen.getByText("网页")).toBeTruthy();

    // 标题本身就是链接
    const titleLink = screen.getByRole("link", {
      name: "国务院办公厅关于2026年部分节假日安排的通知",
    });
    expect(titleLink.getAttribute("href")).toBe("https://www.gov.cn/zhengce/content_7047091.htm");
    expect(titleLink.getAttribute("target")).toBe("_blank");

    // 展开后还能看到完整 URL
    expandSource(0);
    const urlLink = screen.getByRole("link", {
      name: "https://www.gov.cn/zhengce/content_7047091.htm",
    });
    expect(urlLink.getAttribute("href")).toBe("https://www.gov.cn/zhengce/content_7047091.htm");
    expect(urlLink.getAttribute("target")).toBe("_blank");
  });

  it("带上发布时间与摘要", () => {
    render(<SourceCitations sources={[WEB_SOURCE]} />);
    expandSource(0);

    expect(screen.getByText(/2025-11-04/)).toBeTruthy();
    expect(screen.getByText(/春节 2 月 15 日至 2 月 23 日放假调休/)).toBeTruthy();
  });

  it("网页来源没有相似度：不显示百分比", () => {
    render(<SourceCitations sources={[WEB_SOURCE]} />);

    expect(screen.queryByText(/%/)).toBeNull();
  });
});

describe("SourceCitations — 编号与混排", () => {
  it("编号等于在列表中的位置：知识库在前、网页在后", () => {
    render(<SourceCitations sources={[DOC_SOURCE, WEB_SOURCE]} />);

    expect(screen.getByText("来源1:")).toBeTruthy();
    expect(screen.getByText("来源2:")).toBeTruthy();
    expect(screen.getByText("policy.md")).toBeTruthy();
    // 网页那条排在后面，说明位置即编号、没有第二套编号
    const headers = Array.from(document.querySelectorAll(".ant-collapse-header")).map(
      (el) => el.textContent ?? ""
    );
    expect(headers[0]).toContain("policy.md");
    expect(headers[1]).toContain("国务院办公厅关于2026年部分节假日安排的通知");
  });

  it("没有网页来源时行为不变（向量来源照旧显示相似度）", () => {
    render(<SourceCitations sources={[DOC_SOURCE]} />);

    expect(screen.getByText("来源1:")).toBeTruthy();
    expect(screen.getByText(/90.0%/)).toBeTruthy();
    expect(screen.queryByText("网页")).toBeNull();
  });

  it("网页来源缺链接时不崩，也不生成假链接", () => {
    render(<SourceCitations sources={[{ kind: "web", filename: "无链接结果", title: "无链接结果" }]} />);
    expandSource(0);

    expect(screen.getByText("无链接结果")).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
