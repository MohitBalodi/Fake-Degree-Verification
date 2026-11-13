from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.institution import Institution


class Role(StrEnum):
    ADMIN = "admin"
    INSTITUTION = "institution"
    VERIFIER = "verifier"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'institution', 'verifier')", name="ck_users_role"),
        # Institution users must belong to an institution; others must not.
        CheckConstraint(
            "(role = 'institution') = (institution_id IS NOT NULL)",
            name="ck_users_institution_link",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)

    institution: Mapped[Institution | None] = relationship(lazy="joined")
