"""Executable security scope for Formal new exposure.

Research may cover the wider A-share market, but Formal BUY / staged ADD is
restricted to Shanghai and Shenzhen main-board ordinary A-shares.
"""
from __future__ import annotations

import re
from typing import Any

SH_MAIN_A_PREFIXES = ("600", "601", "603", "605")
SZ_MAIN_A_PREFIXES = ("000", "001", "002", "003")
_ALLOWED_PREFIXES = SH_MAIN_A_PREFIXES + SZ_MAIN_A_PREFIXES
_CODE_RE = re.compile(r"^(?:(SH|SZ|BJ))?(\d{6})(?:\.(SH|SZ|BJ))?$")


def normalize_security_code(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    match = _CODE_RE.fullmatch(text)
    if not match:
        return ""
    lead, digits, trail = match.groups()
    if lead and trail and lead != trail:
        return ""
    return digits


def is_formal_new_exposure_tradable(value: Any) -> bool:
    text = str(value or "").strip().upper().replace(" ", "")
    match = _CODE_RE.fullmatch(text)
    if not match:
        return False
    lead, digits, trail = match.groups()
    if lead and trail and lead != trail:
        return False
    market = lead or trail
    if market == "BJ":
        return False
    if market == "SH" and not digits.startswith(SH_MAIN_A_PREFIXES):
        return False
    if market == "SZ" and not digits.startswith(SZ_MAIN_A_PREFIXES):
        return False
    return digits.startswith(_ALLOWED_PREFIXES)


def formal_new_exposure_rejection_reason(value: Any) -> str:
    return "" if is_formal_new_exposure_tradable(value) else "FORMAL_NEW_EXPOSURE_SH_SZ_MAIN_BOARD_ONLY"
