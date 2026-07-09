"""SQLAlchemy ORM models (voiceai schema).

Importing this package registers every model on ``Base.metadata`` so Alembic
autogeneration and ``create_all`` see the full schema.
"""

from app.db.models.analytics import AnalyticsEvent
from app.db.models.audit_log import AuditLog
from app.db.models.enums import Channel, InputType, Rating, Role
from app.db.models.feedback import Feedback
from app.db.models.message import Message
from app.db.models.retrieval import Retrieval
from app.db.models.session import Session
from app.db.models.user_preference import UserPreference

__all__ = [
    "AnalyticsEvent",
    "AuditLog",
    "Channel",
    "Feedback",
    "InputType",
    "Message",
    "Rating",
    "Retrieval",
    "Role",
    "Session",
    "UserPreference",
]
