"""Institution registry: create, bulk import, list, get."""

import csv
import io
import uuid
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import Certificate, CertificateStatus, Institution, Role, User
from app.schemas.certificates import CSV_COLUMNS, CertificateFields, CertificateImportRow
from app.services import audit
from app.services.normalize import normalize_id
from app.services.signing import (
    CertificateRecord,
    SigningKeyMissing,
    load_private_key,
    sign_record,
)


def _institution_of(user: User) -> Institution:
    if user.role != Role.INSTITUTION or user.institution is None:
        raise AppError(403, "forbidden", "Only institution users can add certificates.")
    return user.institution


def _signing_key(institution: Institution) -> Ed25519PrivateKey:
    try:
        return load_private_key(institution.code)
    except SigningKeyMissing as exc:
        raise AppError(
            500, "signing_key_missing", f"No signing key configured for {institution.code}."
        ) from exc


def _build(
    institution: Institution, key: Ed25519PrivateKey, data: CertificateFields
) -> Certificate:
    record = CertificateRecord(
        cert_number=data.cert_number,
        institution_code=institution.code,
        student_name=data.student_name,
        roll_number=data.roll_number,
        programme=data.programme,
        year_of_passing=data.year_of_passing,
        cgpa=data.cgpa,
        marks=data.marks,
        issue_date=data.issue_date,
    )
    return Certificate(
        id=uuid.uuid4(),
        cert_number=data.cert_number,
        institution_id=institution.id,
        student_name=data.student_name,
        roll_number=data.roll_number,
        programme=data.programme,
        year_of_passing=data.year_of_passing,
        cgpa=data.cgpa,
        marks=data.marks,
        issue_date=data.issue_date,
        signature=sign_record(key, record),
        status=CertificateStatus.ACTIVE.value,
    )


def _duplicate_error() -> AppError:
    return AppError(409, "duplicate_cert_number", "A certificate with this number already exists.")


def create_certificate(db: Session, user: User, data: CertificateFields) -> Certificate:
    institution = _institution_of(user)
    if db.scalar(select(Certificate.id).where(Certificate.cert_number == data.cert_number)):
        raise _duplicate_error()

    cert = _build(institution, _signing_key(institution), data)
    db.add(cert)
    audit.record(
        db,
        actor_id=user.id,
        action="certificate.create",
        entity="certificate",
        entity_id=str(cert.id),
        meta={"cert_number": cert.cert_number, "institution_code": institution.code},
    )
    try:
        db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent insert
        db.rollback()
        raise _duplicate_error() from exc
    db.refresh(cert)
    return cert


# --- CSV import ---------------------------------------------------------------


def _row_error(row: int, field: str | None, message: str) -> dict[str, Any]:
    return {"row": row, "field": field, "message": message}


def _pydantic_errors(row: int, exc: ValidationError) -> list[dict[str, Any]]:
    out = []
    for e in exc.errors():
        field = str(e["loc"][0]) if e["loc"] else None
        if e["type"].startswith("date_"):
            message = "Use the format YYYY-MM-DD, e.g. 2024-07-20."
        else:
            message = e["msg"].removeprefix("Value error, ")
            message = message[:1].upper() + message[1:]
        out.append(_row_error(row, field, message))
    return out


def _csv_invalid(message: str, rows: list[dict[str, Any]] | None = None) -> AppError:
    return AppError(422, "csv_invalid", message, rows=rows or [])


def _parse_csv(content: bytes) -> csv.DictReader[str]:
    if len(content) > settings.import_max_mb * 1024 * 1024:
        raise _csv_invalid(f"File is larger than {settings.import_max_mb} MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _csv_invalid("File is not valid UTF-8 text.") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in CSV_COLUMNS if c not in header]
    unknown = [h for h in header if h not in CSV_COLUMNS]
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing columns: {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown columns: {', '.join(unknown)}")
        raise _csv_invalid(
            f"Header is wrong ({'; '.join(parts)}). Expected: {','.join(CSV_COLUMNS)}"
        )
    reader.fieldnames = header
    return reader


def import_csv(db: Session, user: User, content: bytes, filename: str | None) -> int:
    """Validate every row; insert all of them or none. Returns the number imported."""
    institution = _institution_of(user)
    reader = _parse_csv(content)

    errors: list[dict[str, Any]] = []
    valid: list[tuple[int, CertificateImportRow]] = []
    first_seen: dict[str, int] = {}

    for raw in reader:
        line = reader.line_num
        if None in raw:  # more cells than header columns
            errors.append(_row_error(line, None, "Row has more cells than the header."))
            continue
        values = {k: (v or "").strip() for k, v in raw.items()}
        if not any(values.values()):
            continue  # blank line made of commas
        if len(valid) + len(errors) >= settings.import_max_rows:
            raise _csv_invalid(f"File has more than {settings.import_max_rows} rows.")

        try:
            row = CertificateImportRow.model_validate(values)
        except ValidationError as exc:
            errors.extend(_pydantic_errors(line, exc))
            continue

        if row.institution_code != institution.code:
            errors.append(
                _row_error(
                    line,
                    "institution_code",
                    f"Row is for institution {row.institution_code}; "
                    f"you can only import for {institution.code}.",
                )
            )
            continue
        if row.cert_number in first_seen:
            errors.append(
                _row_error(
                    line,
                    "cert_number",
                    f"Duplicate of row {first_seen[row.cert_number]} in this file.",
                )
            )
            continue
        first_seen[row.cert_number] = line
        valid.append((line, row))

    if valid:
        existing = set(
            db.scalars(
                select(Certificate.cert_number).where(
                    Certificate.cert_number.in_([r.cert_number for _, r in valid])
                )
            )
        )
        for line, row in valid:
            if row.cert_number in existing:
                errors.append(_row_error(line, "cert_number", "Already exists in the registry."))

    if errors:
        errors.sort(key=lambda e: e["row"])
        bad_rows = len({e["row"] for e in errors})
        raise _csv_invalid(
            f"{bad_rows} row(s) have errors. Nothing was imported — fix them and upload again.",
            errors,
        )
    if not valid:
        raise _csv_invalid("The file has no data rows.")

    key = _signing_key(institution)
    db.add_all(_build(institution, key, row) for _, row in valid)
    audit.record(
        db,
        actor_id=user.id,
        action="certificate.import",
        entity="certificate",
        meta={"count": len(valid), "filename": filename, "institution_code": institution.code},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409, "duplicate_cert_number", "Some certificates were added meanwhile; upload again."
        ) from exc
    return len(valid)


# --- read ---------------------------------------------------------------------


def _scope(stmt, user: User):  # type: ignore[no-untyped-def]
    """Institution users only ever see their own institution's certificates."""
    if user.role == Role.INSTITUTION:
        return stmt.where(Certificate.institution_id == user.institution_id)
    return stmt


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_certificates(
    db: Session, user: User, *, q: str | None, page: int, size: int
) -> tuple[list[Certificate], int]:
    stmt = _scope(select(Certificate), user)
    if q and q.strip():
        conditions = [Certificate.student_name.ilike(f"%{_escape_like(q.strip())}%", escape="\\")]
        q_id = normalize_id(q)
        if q_id:
            pattern = f"%{_escape_like(q_id)}%"
            conditions += [
                Certificate.cert_number.like(pattern, escape="\\"),
                Certificate.roll_number.like(pattern, escape="\\"),
            ]
        stmt = stmt.where(or_(*conditions))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Certificate.created_at.desc(), Certificate.cert_number)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return list(items), total


def get_certificate(db: Session, user: User, certificate_id: uuid.UUID) -> Certificate:
    cert = db.scalar(_scope(select(Certificate).where(Certificate.id == certificate_id), user))
    if cert is None:
        # Same answer for "doesn't exist" and "belongs to another institution".
        raise AppError(404, "not_found", "Certificate not found.")
    return cert
