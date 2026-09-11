"""用量统计相关 schemas"""

from typing import List, Optional

from pydantic import BaseModel


class UsageTotals(BaseModel):
    """一段时间范围内的真实用量合计（不含估算行与失败行）"""

    requests: int = 0
    """问答次数：一次提问算一次（只数主回答调用）"""

    llm_calls: int = 0
    """模型调用次数：含改写、压缩、Text-to-SQL、工具轮在内的全部调用"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageExcluded(BaseModel):
    """被排除出统计的调用数，仅用于提示数据是否完整，不参与任何合计"""

    estimated_calls: int = 0


class UsageAgentRow(BaseModel):
    """按智能体聚合的一行明细"""

    agent_id: Optional[int] = None
    agent_name: str
    requests: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    last_called_at: Optional[str] = None


class UsagePoint(BaseModel):
    """时间序列上的一个时间桶（无数据时各计数为 0）"""

    bucket: str
    requests: int = 0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageTimeseries(BaseModel):
    """按日/月/年的时间序列，时间桶连续且已补零"""

    granularity: str
    start: str
    end: str
    points: List[UsagePoint] = []


class UsageOverview(BaseModel):
    """用量总览：范围 + 合计 + 排除情况 + 按智能体明细（按总 token 降序）"""

    start: str
    end: str
    totals: UsageTotals
    excluded: UsageExcluded
    agents: List[UsageAgentRow] = []
