"""Read-only delivery of the bounded H1 V4 handoff to the existing web API.

Fetching a newer GitHub manifest is not proof of newer market/account data.
All actionable fields remain restricted by the original H1 fail-closed contract.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

HANDOFF = "data/investor_chatgpt_handoff/latest.json"
CONTRACT = "GEN_GE_INVESTOR_CHATGPT_HANDOFF_V1"
MAX_BYTES = 262144
_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRADE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _parse_manifest(raw: bytes) -> dict[str, Any]:
    if len(raw) > MAX_BYTES:
        raise ValueError("H1 manifest exceeds bounded limit")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("contract_version") != CONTRACT:
        raise ValueError("H1 manifest missing or unsupported contract")
    for field in ("snapshot_id", "canonical_snapshot_id", "canonical_source_run_id", "generated_at"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise ValueError("H1 manifest identity incomplete")
    if not isinstance(value.get("market_session_as_of"), str) or not _TRADE_DATE.fullmatch(value["market_session_as_of"]):
        raise ValueError("H1 market session date invalid")
    if value.get("no_auto_trade") is not True or value.get("formal_buy_now") != [] or value.get("formal_wait_price") != []:
        raise ValueError("H1 manifest cannot authorize execution")
    holdings, trends = value.get("holdings"), value.get("trend_research")
    if not isinstance(holdings, list) or len(holdings) > 16 or not all(isinstance(x, dict) and x.get("executable_shares") == 0 for x in holdings):
        raise ValueError("H1 holdings must remain bounded/read-only")
    if not isinstance(trends, list) or len(trends) > 5:
        raise ValueError("H1 trends must remain bounded")
    feeds, source_files = value.get("feeds"), value.get("source_files")
    if not isinstance(feeds, dict) or not isinstance(source_files, dict) or not isinstance(feeds.get("market_eod"), dict):
        raise ValueError("H1 source or freshness metadata absent")
    if feeds["market_eod"].get("as_of") != value["market_session_as_of"]:
        raise ValueError("H1 market/feed dates disagree")
    if not isinstance(source_files.get("dashboard"), dict) or "sha256" not in source_files["dashboard"]:
        raise ValueError("H1 publication-time dashboard source missing")
    for name, source in source_files.items():
        if not isinstance(name, str) or not isinstance(source, dict):
            raise ValueError("Malformed H1 source reference")
        if "sha256" not in source:
            if source.get("status") != "MISSING":
                raise ValueError("H1 missing source status invalid")
            continue
        if not (_SHA256.fullmatch(str(source.get("sha256", "")))
                and _SHA1.fullmatch(str(source.get("immutable_git_blob_sha", "")))):
            raise ValueError("H1 original-source hashes invalid")
        url = source.get("immutable_blob_url")
        if not isinstance(url, str):
            raise ValueError("H1 immutable source URL missing")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "api.github.com"
                or not re.fullmatch(
                    r"/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/git/blobs/"
                    + re.escape(source["immutable_git_blob_sha"]), parsed.path
                ) or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("H1 immutable source URL invalid")
    if not isinstance(value.get("blocking_reasons"), list) or not all(
        isinstance(x, str) for x in value["blocking_reasons"]
    ):
        raise ValueError("H1 source blockers absent")
    return value


def _request_github_main(repo: str, opener: Callable[..., Any]) -> tuple[dict[str, Any], str]:
    if not _REPO.fullmatch(repo) or ".." in repo or repo.startswith((".", "-")):
        raise ValueError("INVESTOR_V4_GITHUB_REPO invalid")
    owner, name = repo.split("/", 1)
    url = ("https://api.github.com/repos/" + quote(owner, safe="") + "/"
           + quote(name, safe="") + "/contents/" + HANDOFF + "?ref=main")
    request = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "genge-investor-v4-read-only/1.0",
    })
    with opener(request, timeout=6) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Oversized GitHub Contents response")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("encoding") != "base64" or data.get("path") != HANDOFF:
        raise ValueError("Unexpected GitHub Contents response")
    payload = base64.b64decode(str(data.get("content") or ""), validate=False)
    if len(payload) > MAX_BYTES or not _SHA1.fullmatch(str(data.get("sha") or "")):
        raise ValueError("Unverified GitHub Contents blob")
    if _git_blob_sha(payload) != data["sha"]:
        raise ValueError("GitHub blob and payload disagree")
    return _parse_manifest(payload), data["sha"]


def _local(root: Path) -> dict[str, Any] | None:
    path = root / HANDOFF
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        return None
    try:
        return _parse_manifest(path.read_bytes())
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        return None


def latest_report(
    *,
    root: Path | None = None,
    repo: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Always return honest delivery and per-feed state; never a tradable order."""
    root = root if root is not None else Path(__file__).resolve().parents[2]
    repo = (repo if repo is not None else os.getenv("INVESTOR_V4_GITHUB_REPO", "")).strip()
    report: dict[str, Any] | None = None
    delivery = "UNAVAILABLE"
    remote_blob: str | None = None
    warning: str | None = None
    if repo:
        try:
            report, remote_blob = _request_github_main(repo, opener)
            delivery = "GITHUB_MAIN_READ"
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, UnicodeError,
                json.JSONDecodeError) as exc:
            # Never expose a network URL/token, traceback or stale data as fresh.
            warning = "GITHUB_MAIN_UNAVAILABLE_OR_INVALID"
    if report is None:
        report = _local(root)
        if report is not None:
            delivery = "LOCAL_DATED_FALLBACK" if repo else "LOCAL_DATED_ONLY"
            warning = warning or "LIVE_GITHUB_MAIN_NOT_CONFIGURED"
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if report is None:
        return {
            "status": "UNAVAILABLE", "delivery": delivery,
            "retrieved_at": retrieved_at, "hand_off": None,
            "opening_decision_ready": False, "execution_allowed": False,
            "warnings": [warning or "NO_VERIFIED_H1_MANIFEST"],
        }
    return {
        "status": "AVAILABLE_DATED_READ_ONLY", "delivery": delivery,
        "retrieved_at": retrieved_at, "remote_manifest_blob_sha": remote_blob,
        "hand_off": report, "opening_decision_ready": False,
        "execution_allowed": False,
        "warnings": [warning] if warning else [],
    }
