"""ORM 模型包 — 统一注册所有模型，保证 SQLAlchemy relationship 可正确解析"""

from app.models.user import User
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.knowledge_document import KnowledgeDocument
from app.models.agent import Agent, AgentKnowledgeBase
from app.models.data_source import DataSource
from app.models.knowledge_base import KnowledgeBase
from app.models.qa_item import QAItem
from app.models.db_table import DBTable, DBTableField, DBKnowledgePoint

__all__ = [
    "User",
    "Conversation",
    "Message",
    "KnowledgeDocument",
    "Agent",
    "AgentKnowledgeBase",
    "DataSource",
    "KnowledgeBase",
    "QAItem",
    "DBTable",
    "DBTableField",
    "DBKnowledgePoint",
]
