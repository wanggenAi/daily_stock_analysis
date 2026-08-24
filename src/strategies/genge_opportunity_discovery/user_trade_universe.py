"""User-specific executable trade universe for the V3.1 research pipeline.

Formal V3.1 candidates are restricted to Shanghai A-shares and Shenzhen
A-shares that the user can actually trade.  This gate is deliberately applied
before qualitative V3.1 scoring so unsupported markets cannot consume review
capacity or accidentally surface as executable candidates.
"""
from __future__ import annotations

import re
from typing import Any

# Shanghai main board + STAR Market ordinary A-share prefixes.
SH_A_PREFIXES = ("600", "601", "603", "605", "688", "689")
# Shenzhen main board + ChiNext ordinary A-share prefixes.
SZ_A_PREFIXES = ("000", "001", "002", "003", "300", "301")

_ALLOWED_PREFIXES = SH_A_PREFIXES + SZ_A_PREFIXES
_CODE_PATTERN = re.compile(r"^(?:(SH|SZ|BJ))?(\d{6})(?:\.(SH|SZ|BJ))?$")


def normalize_security_code(value: Any) -> str:
    """Normalize supported six-digit security-code representations.

    Accepted examples include ``600000``, ``600000.SH``, ``SH600000`` and
    their SZ/BJ equivalents.  Invalid or ambiguous values return an empty
    string rather than being guessed.
    """
    text = str(value or "").strip().upper().replace(" ", "")
    match = _CODE_PATTERN.fullmatch(text)
    if not match:
        return ""
    leading_market, digits, trailing_market = match.groups()
    if leading_market and trailing_market and leading_market != trailing_market:
        return ""
    return digits


def is_user_tradable_a_share(value: Any) -> bool:
    """Return True only for the user's executable Shanghai/Shenzhen A-shares."""
    text = str(value or "").strip().upper().replace(" ", "")
    match = _CODE_PATTERN.fullmatch(text)
    if not match:
        return False
    leading_market, digits, trailing_market = match.groups()
    if leading_market and trailing_market and leading_market != trailing_market:
        return False
    explicit_market = leading_market or trailing_market
    if explicit_market == "BJ":
        return False
    if explicit_market == "SH" and not digits.startswith(SH_A_PREFIXES):
        return False
    if explicit_market == "SZ" and not digits.startswith(SZ_A_PREFIXES):
        return False
    return digits.startswith(_ALLOWED_PREFIXES)


def trade_universe_rejection_reason(value: Any) -> str:
    """Stable audit reason used by reports/tests when a security is rejected."""
    if is_user_tradable_a_share(value):
        return ""
    return "USER_TRADE_UNIVERSE_SH_SZ_A_ONLY"
