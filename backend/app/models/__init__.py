"""ORM 模型包 — 统一注册所有模型，保证 SQLAlchemy relationship 可正确解析"""

from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.knowledge_document import KnowledgeDocument
from app.models.agent import Agent, AgentKnowledgeBase

__all__ = ["User", "Conversation", "Message", "KnowledgeDocument", "Agent", "AgentKnowledgeBase"]
