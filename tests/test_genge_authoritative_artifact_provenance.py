from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.actions_provenance import (
    EVERY_INDUSTRY_WORKFLOW,
    ONE_SHOT_WORKFLOW,
    OPPORTUNITY_DISCOVERY_WORKFLOW,
)
from src.strategies.genge_opportunity_discovery.authoritative_artifact_provenance import (
    validate_authoritative_artifact,
)
from src.strategies.genge_opportunity_discovery.canonical_authority import finalize_canonical
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _run(
    run_id: int,
    *,
    name: str,
    sha: str,
    conclusion: str | None = "success",
) -> dict:
    return {
        "id": run_id,
        "name": name,
        "head_sha": sha,
        "conclusion": conclusion,
    }


def _snapshot(*, one_shot: bool = False) -> dict:
    source_kind = ONE_SHOT_WORKFLOW if one_shot else "every-industry"
    upstream = "self:101" if one_shot else "202"
    discovery = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "industry": "银行",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "quant_score": "88",
            "latest_trade_date": "2026-08-31",
        }
    ]
    deep_review = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "industry": "银行",
            "v31_execution_universe_status": "EXECUTION_ELIGIBLE",
            "v31_review_rank": "1",
            "latest_trade_date": "2026-08-31",
        }
    ]
    production = [
        {
            "code": "600000",
            "stock_name": "浦发银行",
            "decision_scope": "CANDIDATE",
            "production_action": "HOLD_REVIEW",
            "production_model_version": PRODUCTION_VERSION,
            "v311_production_bridge": PRODUCTION_BRIDGE,
            "strict_pit_refresh_applied": "True",
            "upstream_policy_reused": "False",
            "no_auto_trade": "True",
            "current_price": "10.00",
            "decision_date": "2026-08-31",
            "price_date": "2026-08-31",
        }
    ]
    return build_snapshot(
        discovery,
        deep_review,
        production,
        source_kind=source_kind,
        source_run_id="101",
        upstream_run_id=upstream,
        generated_at="2026-09-01T00:00:00+00:00",
        research_as_of="2026-09-01T00:00:00+00:00",
        source_hashes={
            "discovery_csv": "a" * 64,
            "deep_review_csv": "b" * 64,
            "production_csv": "c" * 64,
        },
    )


def _artifact(tmp_path: Path, *, one_shot: bool = False) -> Path:
    snapshot = _snapshot(one_shot=one_shot)
    source = tmp_path / "source.json"
    source.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    root = tmp_path / "authoritative"
    finalize_canonical(
        source,
        root,
        expected_source_run_id="101",
        source_workflow=ONE_SHOT_WORKFLOW if one_shot else EVERY_INDUSTRY_WORKFLOW,
        expected_source_kind=ONE_SHOT_WORKFLOW if one_shot else "every-industry",
        source_head_sha="a" * 40,
        finalizer_run_id="303",
        finalizer_code_sha="c" * 40,
        finalized_at="2026-09-01T00:05:00+00:00",
    )
    return root


def test_downloaded_authoritative_artifact_revalidates_full_actions_chain(tmp_path: Path) -> None:
    root = _artifact(tmp_path)
    payloads = {
        "101": _run(101, name=EVERY_INDUSTRY_WORKFLOW, sha="a" * 40),
        "202": _run(202, name=OPPORTUNITY_DISCOVERY_WORKFLOW, sha="b" * 40),
        "303": _run(303, name="GenGe V3.1.1 Production Finalizer", sha="c" * 40),
    }

    def get(url: str, token: str):
        return payloads[url.rsplit("/", 1)[-1]]

    result = validate_authoritative_artifact(
        root,
        repository="owner/repo",
        token="token",
        expected_finalizer_run_id="303",
        api_get=get,
    )
    assert result == {
        "status": "VALID",
        "canonical_snapshot_id": _snapshot()["snapshot_id"],
        "source_run_id": "101",
        "upstream_run_id": "202",
        "finalizer_run_id": "303",
    }


def test_artifact_selected_from_different_finalizer_fails_closed(tmp_path: Path) -> None:
    root = _artifact(tmp_path)
    with pytest.raises(ValueError, match="does not match the selected Finalizer"):
        validate_authoritative_artifact(
            root,
            repository="owner/repo",
            token="token",
            expected_finalizer_run_id="999",
            api_get=lambda url, token: {},
        )


def test_failed_or_deleted_finalizer_cannot_be_replayed(tmp_path: Path) -> None:
    root = _artifact(tmp_path)
    payloads = {
        "101": _run(101, name=EVERY_INDUSTRY_WORKFLOW, sha="a" * 40),
        "202": _run(202, name=OPPORTUNITY_DISCOVERY_WORKFLOW, sha="b" * 40),
        "303": _run(
            303,
            name="GenGe V3.1.1 Production Finalizer",
            sha="c" * 40,
            conclusion="failure",
        ),
    }

    def failed(url: str, token: str):
        return payloads[url.rsplit("/", 1)[-1]]

    with pytest.raises(ValueError, match="not a completed success"):
        validate_authoritative_artifact(
            root,
            repository="owner/repo",
            token="token",
            expected_finalizer_run_id="303",
            api_get=failed,
        )

    def deleted(url: str, token: str):
        if url.endswith("/303"):
            raise ValueError("GitHub Actions workflow run lookup failed with HTTP 404")
        return payloads[url.rsplit("/", 1)[-1]]

    with pytest.raises(ValueError, match="HTTP 404"):
        validate_authoritative_artifact(
            root,
            repository="owner/repo",
            token="token",
            expected_finalizer_run_id="303",
            api_get=deleted,
        )


def test_one_shot_artifact_uses_self_source_without_fake_upstream_lookup(tmp_path: Path) -> None:
    root = _artifact(tmp_path, one_shot=True)
    payloads = {
        "101": _run(101, name=ONE_SHOT_WORKFLOW, sha="a" * 40),
        "303": _run(303, name="GenGe V3.1.1 Production Finalizer", sha="c" * 40),
    }
    requested: list[str] = []

    def get(url: str, token: str):
        run_id = url.rsplit("/", 1)[-1]
        requested.append(run_id)
        return payloads[run_id]

    result = validate_authoritative_artifact(
        root,
        repository="owner/repo",
        token="token",
        expected_finalizer_run_id="303",
        api_get=get,
    )
    assert result["upstream_run_id"] == "self:101"
    assert requested == ["101", "303"]
