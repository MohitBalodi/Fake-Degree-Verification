"""Seed demo users and a fictional institution (synthetic data only).

Run: docker compose exec api python -m app.scripts.seed

Idempotent: existing rows are left as they are, so it is safe to run twice.
"""

import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Certificate, Institution, Role, User
from app.schemas.certificates import CertificateCreate
from app.services.certificates import create_certificate
from app.services.signing import load_or_create_private_key, private_key_path, public_key_pem

DEMO_INSTITUTION = {"code": "NBIT", "name": "Northbridge Institute of Technology (fictional)"}

# (email, password, role, belongs_to_demo_institution)
DEMO_USERS = [
    ("admin@ava.test", "Admin@12345", Role.ADMIN, False),
    ("registrar@nbit.test", "Inst@12345", Role.INSTITUTION, True),
    ("verifier@ava.test", "Verify@12345", Role.VERIFIER, False),
]

# Fictional students. (name, programme code, programme, year, cgpa, marks)
_STUDENTS = [
    ("Aarav Mehta", "CS", "B.Tech Computer Science and Engineering", 2024, "8.72", None),
    ("Diya Kapoor", "CS", "B.Tech Computer Science and Engineering", 2024, "9.14", None),
    ("Kabir Malhotra", "CS", "B.Tech Computer Science and Engineering", 2023, "7.65", None),
    ("Ananya Iyer", "CS", "B.Tech Computer Science and Engineering", 2023, "8.05", None),
    ("Vihaan Chauhan", "EC", "B.Tech Electronics and Communication", 2024, "7.98", None),
    ("Ishita Bansal", "EC", "B.Tech Electronics and Communication", 2024, "8.40", None),
    ("Arjun Saxena", "EC", "B.Tech Electronics and Communication", 2022, "6.91", None),
    ("Meera Pillai", "ME", "B.Tech Mechanical Engineering", 2023, "7.33", None),
    ("Rohan Deshmukh", "ME", "B.Tech Mechanical Engineering", 2022, "8.12", None),
    ("Sanya Arora", "ME", "B.Tech Mechanical Engineering", 2024, "9.01", None),
    ("Kunal Bhatt", "MB", "MBA", 2024, None, "78.40"),
    ("Tara Menon", "MB", "MBA", 2023, None, "82.15"),
    ("Neil Fernandes", "MB", "MBA", 2022, None, "71.90"),
    ("Pooja Rawat", "MT", "M.Tech Data Science", 2024, "8.88", None),
    ("Aditya Joshi", "MT", "M.Tech Data Science", 2023, "8.21", "80.50"),
    ("Zoya Qureshi", "MT", "M.Tech Data Science", 2024, "9.32", None),
    ("Harsh Vardhan", "BC", "BCA", 2023, None, "74.25"),
    ("Riya Sen", "BC", "BCA", 2024, None, "88.60"),
    ("Yash Thakur", "BC", "BCA", 2022, None, "69.75"),
    ("Nandini Rao", "CS", "B.Tech Computer Science and Engineering", 2022, "8.56", None),
]


def demo_certificates() -> list[CertificateCreate]:
    out = []
    for i, (name, code, programme, year, cgpa, marks) in enumerate(_STUDENTS, start=1):
        out.append(
            CertificateCreate(
                cert_number=f"NBIT{year}{code}{i:04d}",
                student_name=name,
                roll_number=f"{str(year - 4)[2:]}{code}{i:03d}",
                programme=programme,
                year_of_passing=year,
                cgpa=Decimal(cgpa) if cgpa else None,
                marks=Decimal(marks) if marks else None,
                issue_date=date(year, 7, 20),
            )
        )
    return out


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

    registrar = db.scalar(select(User).where(User.email == "registrar@nbit.test"))
    assert registrar is not None
    existing = set(db.scalars(select(Certificate.cert_number)))
    created = 0
    for cert in demo_certificates():
        if cert.cert_number not in existing:
            create_certificate(db, registrar, cert)  # signs + writes an audit row
            created += 1
    log.append(f"created {created} demo certificates for {institution.code}")
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
