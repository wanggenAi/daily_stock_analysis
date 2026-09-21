"""Deterministic continuity rules for the V3.1 Deep Calculation workset.

The workset resolver may receive fresh upstream signals that are narrower than
an earlier Deep lineage. Codes with unresolved/UNKNOWN gates or an existing
FAIL gate must not silently disappear merely because a transient upstream queue
no longer emits them. This module only preserves research continuity; it grants
no trading authority and does not turn UNKNOWN into PASS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

_CODE_RE = re.compile(r"\d{6}")


def _code(value: Any) -> str | None:
    text = str(value or "").strip()
    if text.isdigit():
        text = text.zfill(6)
    return text if _CODE_RE.fullmatch(text) else None



def _codes(values: Any) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (list, tuple, set)):
        return []
    result: list[str] = []
    for value in values:
        code = _code(value)
        if code:
            result.append(code)
    return list(dict.fromkeys(result))


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def retained_deep_codes(
    status_payload: Mapping[str, Any] | None,
    profiles_payload: Mapping[str, Any] | None,
) -> list[str]:
    """Return prior-lineage codes that still require deterministic continuity.

    New Deep states persist the exact requested_codes scope. Only profiles
    inside that scope may be retained by gate status.

    Legacy final states may have requested_count and profile_count but not the
    exact list. When requested_count < profile_count, the persisted profiles
    contain a broader universe than the actual Deep request. In that case,
    retain only the codes explicitly named by unresolved_reasons instead of
    sweeping the full profile universe.

    Truly unscoped legacy states keep the historical behavior: every persisted
    profile with a non-PASS gate is retained. This changes only workset scope;
    it never infers PASS or grants Formal authority.
    """
    status = status_payload or {}
    retained: list[str] = []

    unresolved = status.get("unresolved_reasons") or {}
    if isinstance(unresolved, Mapping):
        for raw_code in unresolved:
            code = _code(raw_code)
            if code:
                retained.append(code)

    exact_scope = _codes(status.get("requested_codes"))
    requested_count = _positive_int(status.get("requested_count"))
    profile_count = _positive_int(status.get("profile_count"))
    legacy_bounded_scope = bool(
        not exact_scope
        and requested_count is not None
        and profile_count is not None
        and 0 < requested_count < profile_count
    )

    profiles = (profiles_payload or {}).get("profiles") or {}
    if isinstance(profiles, Mapping) and not legacy_bounded_scope:
        allowed = set(exact_scope) if exact_scope else None
        for raw_code, profile in profiles.items():
            code = _code(raw_code)
            if (
                not code
                or not isinstance(profile, Mapping)
                or (allowed is not None and code not in allowed)
            ):
                continue
            gates = profile.get("gates") or {}
            if not isinstance(gates, Mapping):
                continue
            if any(
                isinstance(gate, Mapping)
                and str(gate.get("status") or "UNKNOWN").upper() != "PASS"
                for gate in gates.values()
            ):
                retained.append(code)

    return list(dict.fromkeys(retained))


def load_retained_deep_codes(
    status_path: str | Path = "data/deep_calculation/latest_status.json",
    profiles_path: str | Path = "data/deep_calculation/latest_profiles.json",
) -> list[str]:
    """Load persisted Deep state fail-closed and return continuity codes."""
    def _load(path: str | Path) -> Mapping[str, Any]:
        candidate = Path(path)
        if not candidate.is_file():
            return {}
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, Mapping) else {}

    return retained_deep_codes(_load(status_path), _load(profiles_path))
