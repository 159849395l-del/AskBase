"""用量统计相关 schemas"""

from pydantic import BaseModel


class UsageTotals(BaseModel):
    """一段时间范围内的真实用量合计（不含估算行与失败行）"""

    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageOverview(BaseModel):
    """用量总览：范围 + 合计"""

    start: str
    end: str
    totals: UsageTotals
