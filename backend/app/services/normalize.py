"""Field normalization. Pure functions, no I/O.

Used both when storing/signing registry records and (later) when comparing
OCR-extracted fields, so equivalent inputs always produce identical values.

OCR confusion fixes (O↔0, I/l↔1, S↔5, B↔8) are deliberately NOT here: they
only apply to OCR output in ID fields and land with field matching (Tier 2).
"""

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^0-9A-Z]")
_TWO_PLACES = Decimal("0.01")


def clean_text(value: str) -> str:
    """Trim and collapse internal whitespace; keep case. Used for display/storage."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", value)).strip()


def normalize_text(value: str) -> str:
    """Trim, collapse spaces, uppercase. Used for names and programmes."""
    return clean_text(value).upper()


def normalize_id(value: str) -> str:
    """Uppercase and strip everything except A–Z/0–9. For cert/roll numbers and codes."""
    return _NON_ALNUM.sub("", normalize_text(value))


def normalize_decimal(value: Decimal | float | int | str | None) -> Decimal | None:
    """Round to two decimals (half-up). `None` / empty string stay `None`."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        # str() first so floats like 8.1 don't carry binary noise into Decimal.
        return Decimal(str(value).strip()).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def format_decimal(value: Decimal | float | int | str | None) -> str | None:
    """Canonical string form of a grade: always two decimals, e.g. '8.50'."""
    d = normalize_decimal(value)
    return None if d is None else f"{d:.2f}"


def normalize_year(value: int | str) -> int:
    return int(str(value).strip())


def format_date(value: date) -> str:
    return value.isoformat()
