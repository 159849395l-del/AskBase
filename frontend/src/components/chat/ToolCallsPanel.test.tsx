/** ToolCallsPanel 组件测试 — 工具调用过程要看得到、可展开 */

import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import ToolCallsPanel from "./ToolCallsPanel";

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

const TOOL_CALLS = [
  { name: "web_search", content: "【可引用的来源】\n[来源3: 国务院通知]\n    https://a.example/1" },
  { name: "get_current_time", content: "2026-09-12 13:20:00" },
];

describe("ToolCallsPanel — 工具调用留痕", () => {
  it("显示工具数量与每个工具名", () => {
    render(<ToolCallsPanel toolCalls={TOOL_CALLS} />);

    expect(screen.getByText(/调用了 2 个工具/)).toBeTruthy();
    expect(screen.getByText("web_search")).toBeTruthy();
    expect(screen.getByText("get_current_time")).toBeTruthy();
  });

  it("展开后能看到结果摘要", () => {
    render(<ToolCallsPanel toolCalls={TOOL_CALLS} />);
    fireEvent.click(document.querySelectorAll(".ant-collapse-header")[0]);

    expect(screen.getByText(/【可引用的来源】/)).toBeTruthy();
  });

  it("没有工具调用时什么都不渲染", () => {
    const { container } = render(<ToolCallsPanel toolCalls={[]} />);

    expect(container.textContent).toBe("");
  });
});
