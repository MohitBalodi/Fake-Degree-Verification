"""SQLAlchemy models. Import every model module here so Alembic autogenerate
sees them on `Base.metadata`."""

from app.core.db import Base
from app.models.audit import AuditLog
from app.models.certificate import Certificate, CertificateStatus
from app.models.institution import Institution
from app.models.user import Role, User

__all__ = ["AuditLog", "Base", "Certificate", "CertificateStatus", "Institution", "Role", "User"]
