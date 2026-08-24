/** chat API 单元测试 — sendChatMessage 请求体与事件分发 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { sendChatMessage } from "./chat";

describe("sendChatMessage — 发送聊天消息", () => {
  const callbacks = {
    onToken: vi.fn(),
    onSources: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
  };

  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.setItem("access_token", "test-token");
    // Mock fetch：ok 且空 SSE 流（一次读即结束）
    mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
        }),
      },
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // 等待 fetch 链上的微任务与 IO 完成
  const flush = () =>
    new Promise<void>((resolve) => {
      Promise.resolve()
        .then(() => Promise.resolve())
        .then(() => setTimeout(() => resolve(), 0));
    });

  it("带品类：body 包含 product_category 字段", async () => {
    sendChatMessage(1, "你好", "羽绒服", callbacks);
    await flush();

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/conversations/1/messages");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      content: "你好",
      product_category: "羽绒服",
    });
  });

  it("不带品类（null）：body 不含 product_category 字段", async () => {
    sendChatMessage(1, "你好", null, callbacks);
    await flush();

    const [, init] = mockFetch.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body).toEqual({ content: "你好" });
    expect("product_category" in body).toBe(false);
  });

  it("请求头携带 Bearer token", async () => {
    sendChatMessage(1, "你好", null, callbacks);
    await flush();

    const [, init] = mockFetch.mock.calls[0];
    expect(init.headers.Authorization).toBe("Bearer test-token");
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("HTTP 错误：回调 onError 并携带后端 detail", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ detail: "服务器内部错误" }),
    });

    sendChatMessage(1, "你好", null, callbacks);
    await flush();

    expect(callbacks.onError).toHaveBeenCalledWith("服务器内部错误");
  });

  it("网络异常（非 Abort）：回调 onError", async () => {
    mockFetch.mockRejectedValue(new Error("网络连接失败"));

    sendChatMessage(1, "你好", null, callbacks);
    await flush();

    expect(callbacks.onError).toHaveBeenCalledWith("网络连接失败");
  });

  it("SSE token 事件：回调 onToken", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      body: {
        getReader: () => {
          const chunks = [
            'event: token\ndata: {"token":"你好"}\n\n',
            'event: token\ndata: {"token":"世界"}\n\n',
          ];
          return {
            read: vi
              .fn()
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[0]) })
              .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode(chunks[1]) })
              .mockResolvedValueOnce({ done: true, value: undefined }),
          };
        },
      },
    });

    sendChatMessage(1, "你好", null, callbacks);
    await flush();

    expect(callbacks.onToken).toHaveBeenNthCalledWith(1, "你好");
    expect(callbacks.onToken).toHaveBeenNthCalledWith(2, "世界");
    expect(callbacks.onError).not.toHaveBeenCalled();
  });
});
