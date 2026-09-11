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


def retained_deep_codes(
    status_payload: Mapping[str, Any] | None,
    profiles_payload: Mapping[str, Any] | None,
) -> list[str]:
    """Return prior-lineage codes that still require deterministic continuity.

    Retain codes named by unresolved_reasons plus every persisted profile with
    any non-PASS gate. In the Deep contract a missing/unrecognized gate status
    is not authority to drop work, so it is retained fail-closed just like
    UNKNOWN/FAIL. Preserve first-seen order and never infer a PASS or Formal
    action.
    """
    retained: list[str] = []

    unresolved = (status_payload or {}).get("unresolved_reasons") or {}
    if isinstance(unresolved, Mapping):
        for raw_code in unresolved:
            code = _code(raw_code)
            if code:
                retained.append(code)

    profiles = (profiles_payload or {}).get("profiles") or {}
    if isinstance(profiles, Mapping):
        for raw_code, profile in profiles.items():
            code = _code(raw_code)
            if not code or not isinstance(profile, Mapping):
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
