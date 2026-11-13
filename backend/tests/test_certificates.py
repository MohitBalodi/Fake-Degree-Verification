from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import AuditLog, Certificate, Institution, User
from app.schemas.certificates import CSV_COLUMNS
from app.services.signing import CertificateRecord, verify_record

URL = "/api/v1/certificates"
IMPORT_URL = "/api/v1/certificates/import"
HEADER = ",".join(CSV_COLUMNS)

Headers = dict[str, dict[str, str]]


def payload(**overrides: Any) -> dict[str, Any]:
    body = {
        "cert_number": "TST-2024-0001",
        "student_name": "  Aarav   Sharma ",
        "roll_number": "21cs001",
        "programme": "B.Tech Computer Science",
        "year_of_passing": 2024,
        "cgpa": "8.5",
        "marks": None,
        "issue_date": "2024-07-15",
    }
    body.update(overrides)
    return body


def csv_bytes(*rows: str, header: str = HEADER) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode()


def upload(client: TestClient, headers: dict[str, str], content: bytes, name: str = "c.csv"):
    return client.post(IMPORT_URL, headers=headers, files={"file": (name, content, "text/csv")})


def row(n: int, code: str = "TST", **kw: str) -> str:
    values = {
        "cert_number": f"TST2024{n:04d}",
        "institution_code": code,
        "student_name": f"Student {n}",
        "roll_number": f"R{n:04d}",
        "programme": "B.Sc Physics",
        "year_of_passing": "2023",
        "cgpa": "7.25",
        "marks": "",
        "issue_date": "2023-08-01",
    }
    values.update(kw)
    return ",".join(values[c] for c in HEADER.split(","))


def count_certs(db: Session) -> int:
    return len(db.scalars(select(Certificate.id)).all())


# --- POST /certificates -------------------------------------------------------


def test_create_normalizes_signs_stores_and_audits(
    client: TestClient, auth_headers: Headers, users: dict[str, User], db: Session
) -> None:
    r = client.post(URL, json=payload(), headers=auth_headers["institution"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cert_number"] == "TST20240001"
    assert body["roll_number"] == "21CS001"
    assert body["student_name"] == "Aarav Sharma"
    assert body["cgpa"] == "8.50"
    assert body["status"] == "active"
    assert body["institution"]["code"] == "TST"

    inst = db.scalar(select(Institution).where(Institution.code == "TST"))
    assert inst is not None
    record = CertificateRecord(
        cert_number=body["cert_number"],
        institution_code="TST",
        student_name=body["student_name"],
        roll_number=body["roll_number"],
        programme=body["programme"],
        year_of_passing=body["year_of_passing"],
        cgpa=body["cgpa"],
        marks=body["marks"],
        issue_date=date.fromisoformat(body["issue_date"]),
    )
    assert verify_record(inst.public_key, record, body["signature"])

    log = db.scalars(select(AuditLog).where(AuditLog.action == "certificate.create")).all()
    assert len(log) == 1
    assert log[0].entity_id == body["id"]
    assert log[0].actor_id == users["institution"].id
    assert "student_name" not in log[0].meta  # no personal data in audit meta


def test_create_duplicate_number_conflicts(client: TestClient, auth_headers: Headers) -> None:
    h = auth_headers["institution"]
    assert client.post(URL, json=payload(), headers=h).status_code == 201
    # Same number after normalization.
    r = client.post(URL, json=payload(cert_number="tst 2024 0001"), headers=h)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_cert_number"


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"cgpa": None, "marks": None}, "cgpa or marks"),
        ({"cgpa": "10.5"}, "cgpa"),
        ({"marks": "101"}, "marks"),
        ({"year_of_passing": 1900}, "year_of_passing"),
        ({"issue_date": "2999-01-01"}, "future"),
        ({"issue_date": "2020-01-01"}, "before the year of passing"),
        ({"cert_number": "--//--"}, "cert_number"),
        ({"student_name": "   "}, "student_name"),
    ],
)
def test_create_rejects_invalid(
    client: TestClient, auth_headers: Headers, overrides: dict[str, Any], fragment: str
) -> None:
    r = client.post(URL, json=payload(**overrides), headers=auth_headers["institution"])
    assert r.status_code == 422
    assert fragment in r.text


@pytest.mark.parametrize("who", ["admin", "verifier"])
def test_only_institution_users_can_create(
    client: TestClient, auth_headers: Headers, who: str
) -> None:
    assert client.post(URL, json=payload(), headers=auth_headers[who]).status_code == 403


def test_create_ignores_attempt_to_pick_another_institution(
    client: TestClient, auth_headers: Headers
) -> None:
    r = client.post(URL, json=payload(institution_code="OTH"), headers=auth_headers["institution"])
    assert r.status_code == 201
    assert r.json()["institution"]["code"] == "TST"


def test_create_without_signing_key_fails_cleanly(
    client: TestClient, auth_headers: Headers, keys_dir
) -> None:
    (keys_dir / "TST.pem").unlink()
    r = client.post(URL, json=payload(), headers=auth_headers["institution"])
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "signing_key_missing"


# --- GET list / detail + cross-institution ------------------------------------


def _seed_two_institutions(client: TestClient, auth_headers: Headers) -> tuple[str, str]:
    mine = client.post(URL, json=payload(), headers=auth_headers["institution"]).json()["id"]
    theirs = client.post(
        URL,
        json=payload(cert_number="OTH-1", student_name="Other Person"),
        headers=auth_headers["other_institution"],
    ).json()["id"]
    return mine, theirs


def test_institution_lists_only_its_own(client: TestClient, auth_headers: Headers) -> None:
    _seed_two_institutions(client, auth_headers)
    body = client.get(URL, headers=auth_headers["institution"]).json()
    assert body["total"] == 1
    assert [c["cert_number"] for c in body["items"]] == ["TST20240001"]


def test_admin_lists_all(client: TestClient, auth_headers: Headers) -> None:
    _seed_two_institutions(client, auth_headers)
    assert client.get(URL, headers=auth_headers["admin"]).json()["total"] == 2


def test_verifier_cannot_browse_registry(client: TestClient, auth_headers: Headers) -> None:
    assert client.get(URL, headers=auth_headers["verifier"]).status_code == 403


def test_get_own_certificate(client: TestClient, auth_headers: Headers) -> None:
    mine, _ = _seed_two_institutions(client, auth_headers)
    r = client.get(f"{URL}/{mine}", headers=auth_headers["institution"])
    assert r.status_code == 200
    assert r.json()["id"] == mine


def test_get_other_institutions_certificate_is_404(
    client: TestClient, auth_headers: Headers
) -> None:
    _, theirs = _seed_two_institutions(client, auth_headers)
    r = client.get(f"{URL}/{theirs}", headers=auth_headers["institution"])
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_can_get_any(client: TestClient, auth_headers: Headers) -> None:
    _, theirs = _seed_two_institutions(client, auth_headers)
    assert client.get(f"{URL}/{theirs}", headers=auth_headers["admin"]).status_code == 200


def test_get_bad_uuid_is_422(client: TestClient, auth_headers: Headers) -> None:
    assert client.get(f"{URL}/not-a-uuid", headers=auth_headers["admin"]).status_code == 422


def test_search_and_pagination(client: TestClient, auth_headers: Headers) -> None:
    h = auth_headers["institution"]
    assert upload(client, h, csv_bytes(*(row(i) for i in range(1, 26)))).status_code == 200

    page1 = client.get(URL, params={"size": 10}, headers=h).json()
    assert (page1["total"], len(page1["items"]), page1["page"]) == (25, 10, 1)
    page3 = client.get(URL, params={"size": 10, "page": 3}, headers=h).json()
    assert len(page3["items"]) == 5

    by_name = client.get(URL, params={"q": "student 7"}, headers=h).json()
    assert [c["student_name"] for c in by_name["items"]] == ["Student 7"]
    # ID search is normalized: punctuation/case don't matter.
    by_number = client.get(URL, params={"q": "tst-2024-0012"}, headers=h).json()
    assert [c["cert_number"] for c in by_number["items"]] == ["TST20240012"]
    by_roll = client.get(URL, params={"q": "r0003"}, headers=h).json()
    assert [c["roll_number"] for c in by_roll["items"]] == ["R0003"]
    # LIKE wildcards are treated literally.
    assert client.get(URL, params={"q": "%"}, headers=h).json()["total"] == 0


def test_page_size_capped_at_100(client: TestClient, auth_headers: Headers) -> None:
    r = client.get(URL, params={"size": 101}, headers=auth_headers["admin"])
    assert r.status_code == 422


# --- POST /certificates/import ------------------------------------------------


def test_import_ok_inserts_all_and_audits_once(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    content = csv_bytes(row(1), row(2, marks="81.5", cgpa=""), row(3))
    r = upload(client, auth_headers["institution"], content, name="batch.csv")
    assert r.status_code == 200, r.text
    assert r.json() == {"imported": 3}
    assert count_certs(db) == 3

    log = db.scalars(select(AuditLog).where(AuditLog.action == "certificate.import")).all()
    assert len(log) == 1
    assert log[0].meta["count"] == 3
    assert log[0].meta["filename"] == "batch.csv"


def test_import_accepts_bom_crlf_and_reordered_columns(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    cols = HEADER.split(",")
    reordered = list(reversed(cols))
    values = dict(zip(cols, row(1).split(","), strict=True))
    content = (
        "﻿" + ",".join(reordered) + "\r\n" + ",".join(values[c] for c in reordered) + "\r\n"
    ).encode()
    r = upload(client, auth_headers["institution"], content)
    assert r.status_code == 200, r.text
    assert count_certs(db) == 1


def test_import_is_all_or_nothing_with_per_row_errors(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    content = csv_bytes(
        row(1),  # line 2: ok
        row(2, cgpa="eleven"),  # line 3: bad number
        row(3, issue_date="15/07/2023"),  # line 4: bad date
        row(4),  # line 5: ok
        row(5, cgpa="", marks=""),  # line 6: no grade
    )
    r = upload(client, auth_headers["institution"], content)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "csv_invalid"
    assert "3 row(s)" in err["message"]
    assert [(e["row"], e["field"]) for e in err["rows"]] == [
        (3, "cgpa"),
        (4, "issue_date"),
        (6, None),
    ]
    assert err["rows"][1]["message"] == "Use the format YYYY-MM-DD, e.g. 2024-07-20."
    assert err["rows"][2]["message"] == "At least one of cgpa or marks is required"
    assert count_certs(db) == 0  # nothing inserted, not even the good rows


def test_import_rejects_rows_for_another_institution(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    r = upload(client, auth_headers["institution"], csv_bytes(row(1), row(2, code="OTH")))
    assert r.status_code == 422
    rows = r.json()["error"]["rows"]
    assert rows == [
        {
            "row": 3,
            "field": "institution_code",
            "message": "Row is for institution OTH; you can only import for TST.",
        }
    ]
    assert count_certs(db) == 0


def test_import_rejects_duplicates_in_file_and_registry(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    h = auth_headers["institution"]
    assert client.post(URL, json=payload(cert_number="TST20240009"), headers=h).status_code == 201
    content = csv_bytes(row(1), row(2), row(1, roll_number="X1"), row(9))
    r = upload(client, h, content)
    assert r.status_code == 422
    rows = r.json()["error"]["rows"]
    assert {(e["row"], e["message"]) for e in rows} == {
        (4, "Duplicate of row 2 in this file."),
        (5, "Already exists in the registry."),
    }
    assert count_certs(db) == 1


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        (csv_bytes(row(1), header=HEADER.replace(",marks", "")), "missing columns: marks"),
        (csv_bytes(row(1) + ",x", header=HEADER + ",extra"), "unknown columns: extra"),
        (csv_bytes(), "no data rows"),
        (b"\xff\xfe\x00bad", "UTF-8"),
    ],
)
def test_import_rejects_bad_files(
    client: TestClient, auth_headers: Headers, content: bytes, fragment: str
) -> None:
    r = upload(client, auth_headers["institution"], content)
    assert r.status_code == 422
    assert fragment in r.json()["error"]["message"]


def test_import_row_with_too_many_cells(client: TestClient, auth_headers: Headers) -> None:
    r = upload(client, auth_headers["institution"], csv_bytes(row(1) + ",oops"))
    assert r.status_code == 422
    assert r.json()["error"]["rows"][0]["message"] == "Row has more cells than the header."


def test_import_row_limit(
    client: TestClient, auth_headers: Headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "import_max_rows", 2)
    r = upload(client, auth_headers["institution"], csv_bytes(row(1), row(2), row(3)))
    assert r.status_code == 422
    assert "more than 2 rows" in r.json()["error"]["message"]


@pytest.mark.parametrize("who", ["admin", "verifier"])
def test_only_institution_users_can_import(
    client: TestClient, auth_headers: Headers, who: str
) -> None:
    assert upload(client, auth_headers[who], csv_bytes(row(1))).status_code == 403


# --- audit_log is append-only -------------------------------------------------


def test_audit_log_rejects_update_and_delete(
    client: TestClient, auth_headers: Headers, db: Session
) -> None:
    client.post(URL, json=payload(), headers=auth_headers["institution"])
    for stmt in ("UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log"):
        nested = db.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text(stmt))
        nested.rollback()
