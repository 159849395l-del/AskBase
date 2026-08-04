"""
Test script — verify LLM & Embedding API connectivity (OpenAI-compatible)
Run: venv\Scripts\python.exe test_api_connectivity.py
"""
import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK 控制台兼容

from app.config import settings

print("=== Config ===")
print(f"LLM base:    {settings.LLM_API_BASE}")
print(f"LLM model:   {settings.LLM_MODEL}")
print(f"Embedding base: {settings.EMBEDDING_API_BASE}")
print(f"Embedding model: {settings.EMBEDDING_MODEL}")
print()

# ====== Test 1: LLM chat (OpenAI-compatible) ======
print("=== Test 1: LLM chat ===")
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    llm = ChatOpenAI(
        model=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        temperature=0.3,
    )
    resp = llm.invoke([HumanMessage(content="回复：你好")])
    print(f"Output: {resp.content[:100]}")
except Exception as e:
    print(f"Exception: {e}")
print()

# ====== Test 2: Embedding (OpenAI-compatible) ======
print("=== Test 2: Embedding ===")
try:
    from langchain_openai import OpenAIEmbeddings

    emb = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.EMBEDDING_API_KEY,
        base_url=settings.EMBEDDING_API_BASE,
        # 百炼端点只接受文本输入，必须禁用 token ID 模式
        check_embedding_ctx_length=False,
    )
    vec = emb.embed_query("测试文本")
    print(f"Dim: {len(vec)}, first 5: {[round(v, 4) for v in vec[:5]]}")
except Exception as e:
    print(f"Exception: {e}")

print("\n=== DONE ===")
