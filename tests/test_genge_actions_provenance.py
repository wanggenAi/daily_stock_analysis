from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.actions_provenance import (
    EVERY_INDUSTRY_WORKFLOW,
    ONE_SHOT_WORKFLOW,
    OPPORTUNITY_DISCOVERY_WORKFLOW,
    require_actions_run_id,
    require_git_sha,
    require_upstream_run_ref,
    validate_actions_run,
    validate_production_provenance,
)


def _run(run_id: int, *, name: str = "Producer", sha: str = "a" * 40, conclusion: str | None = "success") -> dict:
    return {
        "id": run_id,
        "name": name,
        "head_sha": sha,
        "conclusion": conclusion,
    }


def test_run_id_must_be_positive_decimal_actions_identity() -> None:
    assert require_actions_run_id("33456355320") == "33456355320"
    for invalid in ("", "0", "-1", "12.3", "job-123", None):
        with pytest.raises(ValueError, match="workflow run id"):
            require_actions_run_id(invalid)


def test_git_sha_must_be_full_40_hex() -> None:
    assert require_git_sha("A" * 40, field="sha") == "a" * 40
    for invalid in ("deadbeef", "g" * 40, "", None):
        with pytest.raises(ValueError, match="40-hex"):
            require_git_sha(invalid, field="sha")


def test_upstream_reference_is_bound_to_producer_semantics() -> None:
    assert require_upstream_run_ref(
        "202",
        source_run_id="101",
        source_workflow=EVERY_INDUSTRY_WORKFLOW,
    ) == "202"
    assert require_upstream_run_ref(
        "self:101",
        source_run_id="101",
        source_workflow=ONE_SHOT_WORKFLOW,
    ) == "self:101"

    with pytest.raises(ValueError, match="exact self"):
        require_upstream_run_ref(
            "self:999",
            source_run_id="101",
            source_workflow=ONE_SHOT_WORKFLOW,
        )
    with pytest.raises(ValueError, match="workflow run id"):
        require_upstream_run_ref(
            "self:101",
            source_run_id="101",
            source_workflow=EVERY_INDUSTRY_WORKFLOW,
        )
    with pytest.raises(ValueError, match="unsupported canonical source workflow"):
        require_upstream_run_ref(
            "202",
            source_run_id="101",
            source_workflow="Untrusted Producer",
        )


def test_job_id_cannot_be_accepted_as_workflow_run_id() -> None:
    # GitHub resolves workflow runs and jobs in different REST namespaces. A
    # numeric job ID sent to /actions/runs/{id} is a 404 and must fail closed.
    def job_namespace_404(url: str, token: str):
        assert "/actions/runs/987654321" in url
        raise ValueError("GitHub Actions workflow run lookup failed with HTTP 404")

    with pytest.raises(ValueError, match="HTTP 404"):
        validate_actions_run(
            "owner/repo",
            "987654321",
            "token",
            api_get=job_namespace_404,
        )


def test_deleted_or_nonexistent_run_id_fails_closed() -> None:
    def missing(url: str, token: str):
        raise ValueError("GitHub Actions workflow run lookup failed with HTTP 404")

    with pytest.raises(ValueError, match="HTTP 404"):
        validate_actions_run("owner/repo", "123", "token", api_get=missing)


def test_cross_run_mixing_fails_on_workflow_or_sha_mismatch() -> None:
    def wrong_workflow(url: str, token: str):
        return _run(123, name="Wrong Producer", sha="a" * 40)

    with pytest.raises(ValueError, match="workflow mismatch"):
        validate_actions_run(
            "owner/repo",
            "123",
            "token",
            expected_workflow="Expected Producer",
            expected_head_sha="a" * 40,
            api_get=wrong_workflow,
        )

    def wrong_sha(url: str, token: str):
        return _run(123, name="Expected Producer", sha="b" * 40)

    with pytest.raises(ValueError, match="head SHA mismatch"):
        validate_actions_run(
            "owner/repo",
            "123",
            "token",
            expected_workflow="Expected Producer",
            expected_head_sha="a" * 40,
            api_get=wrong_sha,
        )


def test_every_industry_provenance_keeps_source_upstream_and_finalizer_distinct() -> None:
    payloads = {
        "101": _run(101, name=EVERY_INDUSTRY_WORKFLOW, sha="a" * 40),
        "202": _run(202, name=OPPORTUNITY_DISCOVERY_WORKFLOW, sha="b" * 40),
        "303": _run(
            303,
            name="GenGe V3.1.1 Production Finalizer",
            sha="c" * 40,
            conclusion=None,
        ),
    }

    def get(url: str, token: str):
        return payloads[url.rsplit("/", 1)[-1]]

    validate_production_provenance(
        repository="owner/repo",
        token="token",
        source_run_id="101",
        source_workflow=EVERY_INDUSTRY_WORKFLOW,
        source_head_sha="a" * 40,
        upstream_run_id="202",
        finalizer_run_id="303",
        api_get=get,
    )


def test_every_industry_wrong_upstream_workflow_fails_closed() -> None:
    payloads = {
        "101": _run(101, name=EVERY_INDUSTRY_WORKFLOW, sha="a" * 40),
        "202": _run(202, name="Some Other Successful Workflow", sha="b" * 40),
        "303": _run(
            303,
            name="GenGe V3.1.1 Production Finalizer",
            sha="c" * 40,
            conclusion=None,
        ),
    }

    def get(url: str, token: str):
        return payloads[url.rsplit("/", 1)[-1]]

    with pytest.raises(ValueError, match="workflow mismatch"):
        validate_production_provenance(
            repository="owner/repo",
            token="token",
            source_run_id="101",
            source_workflow=EVERY_INDUSTRY_WORKFLOW,
            source_head_sha="a" * 40,
            upstream_run_id="202",
            finalizer_run_id="303",
            api_get=get,
        )


def test_one_shot_self_upstream_reuses_only_the_exact_source_run() -> None:
    payloads = {
        "101": _run(101, name=ONE_SHOT_WORKFLOW, sha="a" * 40),
        "303": _run(
            303,
            name="GenGe V3.1.1 Production Finalizer",
            sha="c" * 40,
            conclusion=None,
        ),
    }
    requested: list[str] = []

    def get(url: str, token: str):
        run_id = url.rsplit("/", 1)[-1]
        requested.append(run_id)
        return payloads[run_id]

    validate_production_provenance(
        repository="owner/repo",
        token="token",
        source_run_id="101",
        source_workflow=ONE_SHOT_WORKFLOW,
        source_head_sha="a" * 40,
        upstream_run_id="self:101",
        finalizer_run_id="303",
        api_get=get,
    )
    assert requested == ["101", "303"]

    with pytest.raises(ValueError, match="exact self"):
        validate_production_provenance(
            repository="owner/repo",
            token="token",
            source_run_id="101",
            source_workflow=ONE_SHOT_WORKFLOW,
            source_head_sha="a" * 40,
            upstream_run_id="self:999",
            finalizer_run_id="303",
            api_get=get,
        )


def test_unsuccessful_source_or_upstream_run_fails_closed() -> None:
    def source_failed(url: str, token: str):
        run_id = url.rsplit("/", 1)[-1]
        if run_id == "101":
            return _run(101, name="Producer", sha="a" * 40, conclusion="failure")
        return _run(int(run_id))

    with pytest.raises(ValueError, match="not a completed success"):
        validate_actions_run(
            "owner/repo",
            "101",
            "token",
            expected_workflow="Producer",
            expected_head_sha="a" * 40,
            api_get=source_failed,
        )

    payloads = {
        "101": _run(101, name=EVERY_INDUSTRY_WORKFLOW, sha="a" * 40),
        "202": _run(202, name=OPPORTUNITY_DISCOVERY_WORKFLOW, sha="b" * 40, conclusion="failure"),
        "303": _run(
            303,
            name="GenGe V3.1.1 Production Finalizer",
            sha="c" * 40,
            conclusion=None,
        ),
    }

    def upstream_failed(url: str, token: str):
        return payloads[url.rsplit("/", 1)[-1]]

    with pytest.raises(ValueError, match="not a completed success"):
        validate_production_provenance(
            repository="owner/repo",
            token="token",
            source_run_id="101",
            source_workflow=EVERY_INDUSTRY_WORKFLOW,
            source_head_sha="a" * 40,
            upstream_run_id="202",
            finalizer_run_id="303",
            api_get=upstream_failed,
        )
