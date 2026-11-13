"""Seed demo users and a fictional institution (synthetic data only).

Run: docker compose exec api python -m app.scripts.seed

Idempotent: existing rows are left as they are, so it is safe to run twice.
"""

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Institution, Role, User
from app.services.signing import load_or_create_private_key, private_key_path, public_key_pem

DEMO_INSTITUTION = {"code": "NBIT", "name": "Northbridge Institute of Technology (fictional)"}

# (email, password, role, belongs_to_demo_institution)
DEMO_USERS = [
    ("admin@ava.test", "Admin@12345", Role.ADMIN, False),
    ("registrar@nbit.test", "Inst@12345", Role.INSTITUTION, True),
    ("verifier@ava.test", "Verify@12345", Role.VERIFIER, False),
]


def seed(db: Session) -> list[str]:
    log: list[str] = []

    institution = db.scalar(select(Institution).where(Institution.code == DEMO_INSTITUTION["code"]))
    if institution is None:
        key = load_or_create_private_key(DEMO_INSTITUTION["code"])
        institution = Institution(**DEMO_INSTITUTION, public_key=public_key_pem(key))
        db.add(institution)
        db.flush()
        log.append(
            f"created institution {institution.code} "
            f"(private key: {private_key_path(institution.code)})"
        )
    else:
        log.append(f"institution {institution.code} already exists")

    for email, password, role, linked in DEMO_USERS:
        if db.scalar(select(User).where(User.email == email)) is not None:
            log.append(f"user {email} already exists")
            continue
        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                role=role.value,
                institution_id=institution.id if linked else None,
            )
        )
        log.append(f"created user {email}")

    db.commit()
    return log


def main() -> int:
    with SessionLocal() as db:
        for line in seed(db):
            print(f"seed: {line}")

    print("\nDemo logins (synthetic data, dev only):")
    print(f"  {'role':<12} {'email':<24} password")
    for email, password, role, _ in DEMO_USERS:
        print(f"  {role.value:<12} {email:<24} {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
