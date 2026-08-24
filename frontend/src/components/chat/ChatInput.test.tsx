/** ChatInput 组件测试 — 品类选择器 */

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

describe("ChatInput — 品类选择器", () => {
  it("categories 渲染为 Select 下拉选项", async () => {
    render(
      <ChatInput categories={["羽绒服", "手机"]} onSend={vi.fn()} isStreaming={false} />
    );

    // placeholder 展示
    expect(screen.getByText("全部品类")).toBeTruthy();

    // 打开下拉框后能看到全部品类选项（rc-select 可能渲染多个同名节点，用 findAll）
    fireEvent.mouseDown(document.querySelector(".ant-select-selector") as Element);
    const options = await screen.findAllByText("羽绒服");
    expect(options.length).toBeGreaterThan(0);
    expect(screen.getAllByText("手机").length).toBeGreaterThan(0);
  });

  it("选择品类后发送：onSend 携带 category", async () => {
    const onSend = vi.fn();
    render(
      <ChatInput categories={["羽绒服", "手机"]} onSend={onSend} isStreaming={false} />
    );

    // 选择"羽绒服"（精确点击 .ant-select-item-option 节点，避免命中重复文本节点）
    fireEvent.mouseDown(document.querySelector(".ant-select-selector") as Element);
    await screen.findAllByText("羽绒服");
    const optionEl = Array.from(
      document.querySelectorAll<HTMLElement>(".ant-select-item-option")
    ).find((el) => el.textContent?.includes("羽绒服"));
    expect(optionEl).toBeTruthy();
    fireEvent.click(optionEl as HTMLElement);

    // 输入内容并发送
    fireEvent.change(screen.getByPlaceholderText(TEXTAREA_PLACEHOLDER), {
      target: { value: "推荐一款保暖的" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));

    expect(onSend).toHaveBeenCalledWith("推荐一款保暖的", "羽绒服", undefined);
  });

  it("未选择品类发送：onSend 的 category 为 undefined", () => {
    const onSend = vi.fn();
    render(
      <ChatInput categories={["羽绒服", "手机"]} onSend={onSend} isStreaming={false} />
    );

    fireEvent.change(screen.getByPlaceholderText(TEXTAREA_PLACEHOLDER), {
      target: { value: "你好" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));

    expect(onSend).toHaveBeenCalledWith("你好", undefined, undefined);
  });

  it("categories 为空：不渲染品类选择器", () => {
    render(<ChatInput categories={[]} onSend={vi.fn()} isStreaming={false} />);

    expect(screen.queryByText("全部品类")).toBeNull();
  });
});
