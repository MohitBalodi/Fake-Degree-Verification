"""Pure tests for normalization + canonical record signing. No DB, no network."""

import dataclasses
import json
from datetime import date
from decimal import Decimal

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.services.normalize import (
    clean_text,
    format_decimal,
    normalize_decimal,
    normalize_id,
    normalize_text,
)
from app.services.signing import (
    CertificateRecord,
    canonical_bytes,
    public_key_pem,
    sign_record,
    verify_record,
)

KEY = Ed25519PrivateKey.generate()
PUB = public_key_pem(KEY)

RECORD = CertificateRecord(
    cert_number="NBIT2024CS0001",
    institution_code="NBIT",
    student_name="Aarav Sharma",
    roll_number="21CS001",
    programme="B.Tech Computer Science",
    year_of_passing=2024,
    cgpa=Decimal("8.50"),
    marks=None,
    issue_date=date(2024, 7, 15),
)

# A different-but-valid value for every field, to prove each is covered.
CHANGES = {
    "cert_number": "NBIT2024CS0002",
    "institution_code": "NBIX",
    "student_name": "Aarav Sharmaa",
    "roll_number": "21CS002",
    "programme": "B.Tech Mechanical",
    "year_of_passing": 2023,
    "cgpa": Decimal("8.51"),
    "marks": Decimal("85.00"),
    "issue_date": date(2024, 7, 16),
}


# --- normalize ---------------------------------------------------------------


def test_normalize_text_trims_collapses_uppercases() -> None:
    assert normalize_text("  ravi \t kumar\n ") == "RAVI KUMAR"


def test_clean_text_keeps_case() -> None:
    assert clean_text("  Ravi   Kumar ") == "Ravi Kumar"


def test_normalize_id_strips_punctuation_and_spaces() -> None:
    assert normalize_id(" nbit-2024/cs.0001 ") == "NBIT2024CS0001"


def test_normalize_id_does_not_apply_ocr_fixes() -> None:
    # O->0 etc. is for OCR output only, never for registry input.
    assert normalize_id("BOSS") == "BOSS"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("8.5", "8.50"), (8.5, "8.50"), (Decimal("8.500"), "8.50"), ("8.555", "8.56"), (9, "9.00")],
)
def test_format_decimal(raw: object, expected: str) -> None:
    assert format_decimal(raw) == expected  # type: ignore[arg-type]


def test_decimal_blank_is_none_and_garbage_raises() -> None:
    assert normalize_decimal("  ") is None
    assert format_decimal(None) is None
    with pytest.raises(ValueError):
        normalize_decimal("eight")


# --- canonical form ----------------------------------------------------------


def test_canonical_bytes_are_sorted_compact_utf8_json() -> None:
    raw = canonical_bytes(RECORD)
    parsed = json.loads(raw)
    assert list(parsed) == sorted(parsed)
    assert b" :" not in raw and b", " not in raw and b": " not in raw
    assert parsed["cgpa"] == "8.50"
    assert parsed["marks"] is None
    assert parsed["student_name"] == "AARAV SHARMA"
    assert parsed["issue_date"] == "2024-07-15"
    assert set(parsed) == {f.name for f in dataclasses.fields(CertificateRecord)}


def test_canonical_keeps_non_ascii_as_utf8() -> None:
    rec = dataclasses.replace(RECORD, student_name="Zoë Müller")
    assert "ZOË MÜLLER".encode() in canonical_bytes(rec)


# --- sign / verify -----------------------------------------------------------


def test_sign_then_verify_passes() -> None:
    sig = sign_record(KEY, RECORD)
    assert "=" not in sig  # base64url, no padding
    assert verify_record(PUB, RECORD, sig)


@pytest.mark.parametrize("field", sorted(CHANGES))
def test_any_changed_field_fails(field: str) -> None:
    sig = sign_record(KEY, RECORD)
    tampered = dataclasses.replace(RECORD, **{field: CHANGES[field]})
    assert not verify_record(PUB, tampered, sig)


def test_wrong_institution_key_fails() -> None:
    sig = sign_record(KEY, RECORD)
    other_pub = public_key_pem(Ed25519PrivateKey.generate())
    assert not verify_record(other_pub, RECORD, sig)


def test_equivalent_inputs_sign_the_same() -> None:
    messy = CertificateRecord(
        cert_number=" nbit-2024-cs-0001 ",
        institution_code="nbit",
        student_name="  aarav   SHARMA ",
        roll_number="21-cs-001",
        programme="b.tech   computer science",
        year_of_passing="2024",  # type: ignore[arg-type]
        cgpa=8.5,
        marks="",
        issue_date=date(2024, 7, 15),
    )
    assert canonical_bytes(messy) == canonical_bytes(RECORD)
    # Ed25519 is deterministic, so the signatures match exactly too.
    assert sign_record(KEY, messy) == sign_record(KEY, RECORD)
    assert verify_record(PUB, messy, sign_record(KEY, RECORD))


@pytest.mark.parametrize("bad", ["", "not base64!!", "AAAA", "x" * 86])
def test_malformed_signature_is_rejected_not_raised(bad: str) -> None:
    assert not verify_record(PUB, RECORD, bad)


def test_bad_public_key_is_rejected_not_raised() -> None:
    assert not verify_record("not a pem", RECORD, sign_record(KEY, RECORD))
