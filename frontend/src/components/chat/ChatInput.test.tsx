/** ChatInput 组件测试 — 知识库选择器与发送行为 */

import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import ChatInput from "./ChatInput";

const TEXTAREA_PLACEHOLDER = "输入您的问题，按 Enter 发送，Shift+Enter 换行...";

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

const KBS = [
  { id: 1, name: "商品FAQ" },
  { id: 2, name: "用户手册" },
];

describe("ChatInput — 知识库选择器", () => {
  it("knowledgeBases 非空：渲染知识库下拉选项", async () => {
    render(<ChatInput knowledgeBases={KBS} onSend={vi.fn()} isStreaming={false} />);

    // 打开下拉框后能看到知识库选项
    fireEvent.mouseDown(document.querySelector(".ant-select-selector") as Element);
    const options = await screen.findAllByText("商品FAQ");
    expect(options.length).toBeGreaterThan(0);
    expect(screen.getAllByText("用户手册").length).toBeGreaterThan(0);
  });

  it("选择知识库后发送：onSend 携带 kbIds", async () => {
    const onSend = vi.fn();
    render(<ChatInput knowledgeBases={KBS} onSend={onSend} isStreaming={false} />);

    // 选择"商品FAQ"（精确点击 .ant-select-item-option 节点，避免命中重复文本节点）
    fireEvent.mouseDown(document.querySelector(".ant-select-selector") as Element);
    await screen.findAllByText("商品FAQ");
    const optionEl = Array.from(
      document.querySelectorAll<HTMLElement>(".ant-select-item-option")
    ).find((el) => el.textContent?.includes("商品FAQ"));
    expect(optionEl).toBeTruthy();
    fireEvent.click(optionEl as HTMLElement);

    // 输入内容并发送
    fireEvent.change(screen.getByPlaceholderText(TEXTAREA_PLACEHOLDER), {
      target: { value: "如何申请退款？" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));

    expect(onSend).toHaveBeenCalledWith("如何申请退款？", [1]);
  });

  it("未选择知识库发送：onSend 的 kbIds 为 undefined", () => {
    const onSend = vi.fn();
    render(<ChatInput knowledgeBases={KBS} onSend={onSend} isStreaming={false} />);

    fireEvent.change(screen.getByPlaceholderText(TEXTAREA_PLACEHOLDER), {
      target: { value: "你好" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));

    expect(onSend).toHaveBeenCalledWith("你好", undefined);
  });

  it("knowledgeBases 为空：不渲染知识库选择器", () => {
    render(<ChatInput knowledgeBases={[]} onSend={vi.fn()} isStreaming={false} />);

    expect(screen.queryByText("全部知识库")).toBeNull();
  });
});
