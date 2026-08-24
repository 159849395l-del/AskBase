/** 聊天 API — SSE 流式问答 */

import type { SourceItem } from "../types/chat";

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onSources: (sources: SourceItem[]) => void;
  onDone: (messageId: number, tokenCount: number) => void;
  onError: (error: string) => void;
}

export function sendChatMessage(
  convId: number,
  content: string,
  callbacks: StreamCallbacks,
  kbDocIds?: number[]
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`/api/conversations/${convId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      content,
      ...(kbDocIds && kbDocIds.length > 0 ? { kb_doc_ids: kbDocIds } : {}),
    }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        callbacks.onError(errData.detail || `HTTP Error ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError("无法读取响应流");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // 按 \n\n 分隔 SSE 事件块
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          if (!part.trim()) continue;

          const lines = part.split("\n");
          let eventType = "";
          let eventData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              eventData = line.slice(6).trim();
            }
          }

          if (!eventData) continue;

          try {
            const parsed = JSON.parse(eventData);

            switch (eventType) {
              case "token":
                callbacks.onToken(parsed.token);
                break;
              case "sources":
                callbacks.onSources(parsed.sources);
                break;
              case "done":
                callbacks.onDone(parsed.message_id, parsed.token_count || 0);
                break;
              case "error":
                callbacks.onError(parsed.error || "未知错误");
                break;
            }
          } catch {
            // 忽略解析异常
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(err.message || "网络错误");
      }
    });

  return controller;
}
