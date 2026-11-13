import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.institution import Institution


class CertificateStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Certificate(Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'revoked')", name="ck_certificates_status"),
        CheckConstraint("cgpa IS NOT NULL OR marks IS NOT NULL", name="ck_certificates_grade"),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)", name="ck_certificates_revoked_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stored in normalized ID form (uppercase, no punctuation) — see services/normalize.py.
    cert_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="RESTRICT"), index=True
    )
    student_name: Mapped[str] = mapped_column(String(255))
    roll_number: Mapped[str] = mapped_column(String(64), index=True)
    programme: Mapped[str] = mapped_column(String(255))
    year_of_passing: Mapped[int] = mapped_column(Integer)
    cgpa: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    # Percentage, 0–100.
    marks: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Ed25519 over the canonical record, base64url without padding.
    signature: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=CertificateStatus.ACTIVE.value)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    institution: Mapped[Institution] = relationship(lazy="joined")
