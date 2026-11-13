"""SQLAlchemy models. Import every model module here so Alembic autogenerate
sees them on `Base.metadata`."""

from app.core.db import Base

__all__ = ["Base"]
