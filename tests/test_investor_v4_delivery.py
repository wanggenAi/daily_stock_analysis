"""The Web read path may display dated H1 evidence, never reauthorize it."""
from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

import pytest

from src.services.investor_v4_delivery import HANDOFF, _git_blob_sha, latest_report


def sample() -> dict:
    sha = "a" * 40
    return {
        "contract_version": "GEN_GE_INVESTOR_CHATGPT_HANDOFF_V1",
        "snapshot_id": "snapshot123",
        "generated_at": "2026-09-28T00:00:00Z",
        "market_session_as_of": "2026-09-24",
        "canonical_snapshot_id": "canonical123",
        "canonical_source_run_id": "123",
        "no_auto_trade": True,
        "formal_buy_now": [],
        "formal_wait_price": [],
        "holdings": [{
            "code": "600406", "name": "历史持仓",
            "recorded_formal_action": "REDUCE_25",
            "executable_shares": 0,
            "frozen_reference_price": 22.27,
            "reference_as_of": "2026-09-24",
        }],
        "trend_research": [{"trend_id": "electrification_infrastructure", "authority": "RESEARCH_ONLY"}],
        "blocking_reasons": ["STALE_OR_UNVERIFIED_MARKET_SESSION"],
        "feeds": {
            "market_eod": {"as_of": "2026-09-24", "status": "STALE_OR_UNVERIFIED"},
            "funds": {"status": "UNVERIFIED"},
            "planning_cash": {"amount_cny": 50000, "status": "DATED_PLANNING_ONLY"},
            "broker_cash": {"amount_cny": None, "status": "UNKNOWN"},
            "executable_quotes": {"status": "UNVERIFIED"},
        },
        "source_files": {
            "dashboard": {
                "path": "data/investor_decision_dashboard/latest.json",
                "sha256": "b" * 64,
                "immutable_git_blob_sha": sha,
                "immutable_blob_url":
                    "https://api.github.com/repos/example/repo/git/blobs/" + sha,
            },
        },
    }


def save_local(tmp_path: Path, manifest: dict | None = None) -> None:
    p = tmp_path / HANDOFF
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest if manifest is not None else sample()), encoding="utf-8")


class FakeResponse:
    def __init__(self, raw: bytes):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, n):
        return self.raw[:n]


def github_opener(manifest: dict, *, tamper_sha: bool = False):
    raw = json.dumps(manifest).encode("utf-8")
    sha = "0" * 40 if tamper_sha else _git_blob_sha(raw)
    content = json.dumps({
        "path": HANDOFF, "sha": sha, "encoding": "base64",
        "content": base64.b64encode(raw).decode("ascii"),
    }).encode("utf-8")
    calls = []

    def fake(request, timeout):
        calls.append((request.full_url, timeout))
        return FakeResponse(content)

    return fake, calls


def test_remote_main_reads_only_fixed_github_contents_without_granting_authority(tmp_path):
    save_local(tmp_path)
    opener, calls = github_opener(sample())
    reply = latest_report(root=tmp_path, repo="example/repo", opener=opener)
    assert reply["status"] == "AVAILABLE_DATED_READ_ONLY"
    assert reply["delivery"] == "GITHUB_MAIN_READ"
    assert len(calls) == 1
    assert calls[0] == (
        "https://api.github.com/repos/example/repo/contents/" + HANDOFF + "?ref=main",
        6,
    )
    assert len(reply["remote_manifest_blob_sha"]) == 40
    assert reply["retrieved_at"].endswith("Z")
    assert reply["hand_off"]["market_session_as_of"] == "2026-09-24"
    assert reply["hand_off"]["holdings"][0]["executable_shares"] == 0
    assert reply["opening_decision_ready"] is False
    assert reply["execution_allowed"] is False
    assert reply["warnings"] == []


def test_mismatched_remote_blob_falls_back_to_explicit_local_snapshot(tmp_path):
    save_local(tmp_path)
    opener, _ = github_opener(sample(), tamper_sha=True)
    reply = latest_report(root=tmp_path, repo="example/repo", opener=opener)
    assert reply["delivery"] == "LOCAL_DATED_FALLBACK"
    assert reply["remote_manifest_blob_sha"] is None
    assert reply["warnings"] == ["GITHUB_MAIN_UNAVAILABLE_OR_INVALID"]
    assert reply["hand_off"]["market_session_as_of"] == "2026-09-24"
    assert not reply["opening_decision_ready"]


def test_no_remote_config_is_explicitly_local_and_never_fakes_latest(tmp_path):
    save_local(tmp_path)
    reply = latest_report(root=tmp_path, repo="")
    assert reply["delivery"] == "LOCAL_DATED_ONLY"
    assert reply["warnings"] == ["LIVE_GITHUB_MAIN_NOT_CONFIGURED"]
    assert not reply["execution_allowed"]


def test_absent_handoff_is_visible_unavailable_not_fabricated(tmp_path):
    reply = latest_report(root=tmp_path, repo="")
    assert reply["status"] == "UNAVAILABLE"
    assert reply["hand_off"] is None
    assert reply["warnings"] == ["NO_VERIFIED_H1_MANIFEST"]
    assert reply["execution_allowed"] is False


def test_reject_malicious_repository_without_external_request(tmp_path):
    save_local(tmp_path)
    def unexpected(*args, **kwargs):
        raise AssertionError("Untrusted URL must never be requested")
    reply = latest_report(root=tmp_path, repo="https://evil.example/repo", opener=unexpected)
    assert reply["delivery"] == "LOCAL_DATED_FALLBACK"
    assert reply["warnings"] == ["GITHUB_MAIN_UNAVAILABLE_OR_INVALID"]


@pytest.mark.parametrize("change", [
    {"formal_buy_now": [{"code": "600519"}]},
    {"formal_wait_price": [{"code": "600519"}]},
    {"no_auto_trade": False},
    {"holdings": [{"code": "600406", "executable_shares": 100}]},
    {"market_session_as_of": "2026-09-25"},
    {"source_files": {}},
])
def test_tampered_or_actionable_h1_cannot_enter_web_api(tmp_path, change):
    payload = {**sample(), **change}
    save_local(tmp_path, payload)
    reply = latest_report(root=tmp_path, repo="")
    assert reply["status"] == "UNAVAILABLE"
    assert reply["hand_off"] is None
    assert not reply["opening_decision_ready"]


def test_untrusted_immutable_source_link_fails_closed(tmp_path):
    s = sample()
    s["source_files"]["dashboard"]["immutable_blob_url"] = "javascript:alert(1)"
    save_local(tmp_path, s)
    result = latest_report(root=tmp_path, repo="")
    assert result["status"] == "UNAVAILABLE"


def test_missing_remote_and_old_local_never_claim_current_market(tmp_path):
    local = copy.deepcopy(sample())
    local["generated_at"] = "2026-09-27T23:17:07Z"
    save_local(tmp_path, local)
    def broken(*args, **kwargs):
        raise TimeoutError("network")
    result = latest_report(root=tmp_path, repo="example/repo", opener=broken)
    assert result["delivery"] == "LOCAL_DATED_FALLBACK"
    assert result["hand_off"]["market_session_as_of"] == "2026-09-24"
    assert result["hand_off"]["feeds"]["market_eod"]["status"] == "STALE_OR_UNVERIFIED"
    assert result["hand_off"]["feeds"]["broker_cash"]["amount_cny"] is None
    assert result["execution_allowed"] is False
