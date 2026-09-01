"""Fail-closed validation for GitHub Actions provenance used by V3.1.1 production.

GitHub Actions workflow run IDs and job IDs are both decimal integers, so format
checks alone cannot distinguish their namespaces. Production therefore validates
persisted run identities against the Actions *workflow-runs* REST endpoint before
canonical authority is published.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_RUN_ID_RE = re.compile(r"^[1-9][0-9]*$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def require_actions_run_id(value: object, *, field: str = "run_id") -> str:
    run_id = str(value or "").strip()
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"{field} must be a positive decimal GitHub Actions workflow run id")
    return run_id


def require_git_sha(value: object, *, field: str) -> str:
    sha = str(value or "").strip()
    if not _SHA_RE.fullmatch(sha):
        raise ValueError(f"{field} must be a full 40-hex Git commit SHA")
    return sha.lower()


def _github_api_get(url: str, token: str) -> Mapping[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "genge-v311-actions-provenance",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed GitHub API host
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"GitHub Actions workflow run lookup failed with HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError("GitHub Actions workflow run lookup failed") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("GitHub Actions workflow run lookup returned a non-object payload")
    return payload


def validate_actions_run(
    repository: str,
    run_id: object,
    token: str,
    *,
    expected_workflow: str = "",
    expected_head_sha: str = "",
    require_success: bool = True,
    api_get: Callable[[str, str], Mapping[str, Any]] | None = None,
) -> Mapping[str, Any]:
    """Validate an ID specifically in the workflow-run namespace.

    A job ID passed here fails closed because ``/actions/runs/{id}`` does not
    resolve it. Deleted/stale/nonexistent run IDs fail for the same reason.
    """
    repository = str(repository or "").strip()
    if not repository or "/" not in repository:
        raise ValueError("repository must be owner/name")
    normalized_run_id = require_actions_run_id(run_id)
    if not str(token or "").strip():
        raise ValueError("GitHub token is required for Actions provenance validation")
    if expected_head_sha:
        expected_head_sha = require_git_sha(expected_head_sha, field="expected_head_sha")

    getter = api_get or _github_api_get
    url = f"https://api.github.com/repos/{repository}/actions/runs/{normalized_run_id}"
    payload = getter(url, token)

    actual_id = require_actions_run_id(payload.get("id"), field="resolved_run_id")
    if actual_id != normalized_run_id:
        raise ValueError("GitHub Actions workflow run id mismatch")
    workflow = str(payload.get("name") or "").strip()
    if expected_workflow and workflow != expected_workflow:
        raise ValueError(
            f"GitHub Actions workflow mismatch: expected {expected_workflow!r}, got {workflow!r}"
        )
    if expected_head_sha:
        actual_sha = require_git_sha(payload.get("head_sha"), field="resolved_head_sha")
        if actual_sha != expected_head_sha:
            raise ValueError("GitHub Actions workflow run head SHA mismatch")
    if require_success and str(payload.get("conclusion") or "") != "success":
        raise ValueError("GitHub Actions workflow run is not a completed success")
    return payload


def validate_production_provenance(
    *,
    repository: str,
    token: str,
    source_run_id: object,
    source_workflow: str,
    source_head_sha: str,
    upstream_run_id: object,
    finalizer_run_id: object,
    finalizer_workflow: str = "GenGe V3.1.1 Production Finalizer",
    api_get: Callable[[str, str], Mapping[str, Any]] | None = None,
) -> None:
    """Validate source, upstream, and current Finalizer run identities."""
    validate_actions_run(
        repository,
        source_run_id,
        token,
        expected_workflow=source_workflow,
        expected_head_sha=source_head_sha,
        require_success=True,
        api_get=api_get,
    )
    validate_actions_run(
        repository,
        upstream_run_id,
        token,
        require_success=True,
        api_get=api_get,
    )
    # The current Finalizer is normally still in_progress, so existence and
    # workflow identity are authoritative; conclusion cannot yet be "success".
    validate_actions_run(
        repository,
        finalizer_run_id,
        token,
        expected_workflow=finalizer_workflow,
        require_success=False,
        api_get=api_get,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--upstream-run-id", required=True)
    parser.add_argument("--finalizer-run-id", required=True)
    parser.add_argument("--finalizer-workflow", default="GenGe V3.1.1 Production Finalizer")
    args = parser.parse_args(argv)
    validate_production_provenance(
        repository=args.repository,
        token=args.token,
        source_run_id=args.source_run_id,
        source_workflow=args.source_workflow,
        source_head_sha=args.source_head_sha,
        upstream_run_id=args.upstream_run_id,
        finalizer_run_id=args.finalizer_run_id,
        finalizer_workflow=args.finalizer_workflow,
    )
    print("GitHub Actions provenance: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
