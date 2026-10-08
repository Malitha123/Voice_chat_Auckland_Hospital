"""
Shared helpers for API routers.

Currently houses phone-number normalization. The seeded patients table
stores phones in two parallel columns:

    phone             "+64211030736"     ← display, with leading "+"
    external_user_id  "64211030736"      ← search key, digits-only

Whatever a user types ("021 103 0736", "+64 21 103 0736", "64211030736")
must collapse to the same canonical form for both lookup and unique-
constraint purposes. ``normalize_phone()`` handles the common New Zealand
patterns and rejects unsupported international numbers.
"""

from __future__ import annotations
import re


def normalize_phone(raw: str | None) -> str:
    """Return a common NZ phone in digits-only E.164 form, or an empty string.

    Accept local 021/022/027 and geographic numbers, +64, 64 and 0064.
    Formatting is ignored; unsupported foreign numbers are rejected.
    """
    if not isinstance(raw, str) or not raw.strip():
        return ""
    # Accept common formatting, not letters, extensions or Unicode digits.
    if not re.fullmatch(r"[+0-9()\s-]+", raw):
        return ""
    digits = re.sub(r"[^0-9]", "", raw)
    if digits.startswith("0064"):
        digits = digits[2:]
    elif digits.startswith("0") and not raw.lstrip().startswith("+"):
        digits = "64" + digits[1:]
    # Common NZ mobile and geographic landline formats. Short codes and
    # overseas numbers cannot identify a patient in this NZ deployment.
    if re.fullmatch(r"64(?:2[0-9]{7,9}|[34679][0-9]{7})", digits):
        return digits
    return ""


def display_phone(canonical: str | None) -> str:
    """
    Render a canonical phone number with the customary ``+`` prefix.

    Inverse of ``normalize_phone()`` for display purposes only — does not
    re-introduce spacing. Returns an empty string for empty input.
    """
    if not canonical:
        return ""
    return "+" + canonical if not canonical.startswith("+") else canonical
