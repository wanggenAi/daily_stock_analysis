"""User-specific executable trade universe for the V3.1 research pipeline.

Formal V3.1 candidates are restricted to Shanghai MAIN BOARD and Shenzhen
MAIN BOARD A-shares that the user can actually trade. ChiNext (创业板), STAR
Market (科创板), Beijing Stock Exchange, ETFs/funds, B-shares and non-A-share
markets are explicitly excluded.

This gate is deliberately applied before qualitative V3.1 scoring so unsupported
securities cannot consume review capacity or accidentally surface as executable
candidates.
"""
from __future__ import annotations

import re
from typing import Any

# Shanghai MAIN BOARD ordinary A-share prefixes only. STAR Market 688/689 excluded.
SH_MAIN_A_PREFIXES = ("600", "601", "603", "605")
# Shenzhen MAIN BOARD ordinary A-share prefixes only. ChiNext 300/301 excluded.
SZ_MAIN_A_PREFIXES = ("000", "001", "002", "003")

_ALLOWED_PREFIXES = SH_MAIN_A_PREFIXES + SZ_MAIN_A_PREFIXES
_CODE_PATTERN = re.compile(r"^(?:(SH|SZ|BJ))?(\d{6})(?:\.(SH|SZ|BJ))?$")


def normalize_security_code(value: Any) -> str:
    """Normalize supported six-digit security-code representations.

    Accepted examples include ``600000``, ``600000.SH`` and ``SH600000``.
    Invalid or ambiguous values return an empty string rather than being guessed.
    Normalization itself does not imply trade eligibility.
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
    """Return True only for Shanghai/Shenzhen MAIN BOARD A-shares."""
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
    if explicit_market == "SH" and not digits.startswith(SH_MAIN_A_PREFIXES):
        return False
    if explicit_market == "SZ" and not digits.startswith(SZ_MAIN_A_PREFIXES):
        return False

    # This prefix check also rejects STAR (688/689), ChiNext (300/301), ETFs,
    # B-shares and other exchange products from the executable universe.
    return digits.startswith(_ALLOWED_PREFIXES)


def trade_universe_rejection_reason(value: Any) -> str:
    """Stable audit reason used by reports/tests when a security is rejected."""
    if is_user_tradable_a_share(value):
        return ""
    return "USER_TRADE_UNIVERSE_SH_SZ_MAIN_A_ONLY"
