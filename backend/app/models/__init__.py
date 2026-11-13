"""SQLAlchemy models. Import every model module here so Alembic autogenerate
sees them on `Base.metadata`."""

from app.core.db import Base
from app.models.institution import Institution
from app.models.user import Role, User

__all__ = ["Base", "Institution", "Role", "User"]
