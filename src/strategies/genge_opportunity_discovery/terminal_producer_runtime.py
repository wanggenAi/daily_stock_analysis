"""GitHub Actions runtime adapter for exact Candidate Terminal producer resolution."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .terminal_producer_lineage import (
    LineageResolutionError,
    TerminalProducerNode,
    resolve_terminal_producer,
)

WORKFLOW_FILE = "genge-candidate-terminal-review.yml"
WORKFLOW_NAME = "GenGe Candidate Terminal Review"
ARTIFACT_NAME = "genge-candidate-terminal-decisions"
MAX_INSPECTED_RUNS = 100
MAX_LINEAGE_HOPS = 12


def _gh_json(repo: str, endpoint: str) -> Any:
    proc = subprocess.run(["gh", "api", f"repos/{repo}/{endpoint}"], check=True, stdout=subprocess.PIPE)
    return json.loads(proc.stdout)


def _gh_bytes(repo: str, endpoint: str) -> bytes:
    proc = subprocess.run(["gh", "api", f"repos/{repo}/{endpoint}"], check=True, stdout=subprocess.PIPE)
    return proc.stdout


def _suffix_run_id(run: dict[str, Any]) -> str:
    title = str(run.get("display_title") or run.get("name") or "")
    match = re.search(r"/\s*(\d+)\s*$", title)
    return match.group(1) if match else ""


def _manifest_lineage_key(manifest: dict[str, Any]) -> str:
    mode = str(manifest.get("lineage_mode") or "")
    if mode == "POSTSCAN":
        upstream = str(manifest.get("upstream_run_id") or "")
        if upstream.isdigit():
            return f"POSTSCAN:{upstream}"
    if mode == "EVERY_INDUSTRY_AUTHORIZED":
        research = str(manifest.get("research_run_id") or "")
        finalizer = str(manifest.get("finalizer_run_id") or "")
        if research.isdigit() and finalizer.isdigit() and manifest.get("finalizer_authority_verified") is True:
            return f"EVERY_INDUSTRY_AUTHORIZED:{research}:{finalizer}"
    return ""


def _metadata_lineage_candidates(run: dict[str, Any]) -> set[str]:
    event = str(run.get("event") or "")
    suffix = _suffix_run_id(run)
    if not suffix:
        return set()
    if event == "workflow_run":
        return {f"POSTSCAN:{suffix}"}
    if event == "workflow_dispatch":
        return {f"POSTSCAN:{suffix}", f"EVERY_INDUSTRY_FINALIZER:{suffix}"}
    return set()


def _manifest_matches_metadata(run: dict[str, Any], manifest: dict[str, Any]) -> bool:
    key = _manifest_lineage_key(manifest)
    if not key:
        return False
    event = str(run.get("event") or "")
    suffix = _suffix_run_id(run)
    if event == "workflow_run":
        return key == f"POSTSCAN:{suffix}"
    if event == "workflow_dispatch":
        mode = str(manifest.get("lineage_mode") or "")
        if mode == "POSTSCAN":
            return str(manifest.get("upstream_run_id") or "") == suffix
        if mode == "EVERY_INDUSTRY_AUTHORIZED":
            return str(manifest.get("finalizer_run_id") or "") == suffix
    return False


def _candidate_identity(rows: list[dict[str, str]]) -> str:
    records = sorted(
        (
            str(row.get("code") or ""),
            str(row.get("terminal_decision") or ""),
            str(row.get("terminal_reason_class") or ""),
        )
        for row in rows
    )
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass
class ArtifactValidation:
    valid: bool
    lineage_key: str = ""
    candidate_identity: str = ""
    reason: str = ""
    files: dict[str, bytes] | None = None


def _single_member(zf: zipfile.ZipFile, basename: str) -> str:
    matches = [name for name in zf.namelist() if Path(name).name == basename and not name.endswith("/")]
    if len(matches) != 1:
        raise ValueError(f"expected one {basename}, found {len(matches)}")
    return matches[0]


def _validate_artifact_bytes(run: dict[str, Any], payload: bytes) -> ArtifactValidation:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            csv_name = _single_member(zf, "candidate_terminal_decisions.csv")
            summary_name = _single_member(zf, "candidate_terminal_summary.json")
            lineage_name = _single_member(zf, "terminal_lineage.json")
            csv_bytes = zf.read(csv_name)
            summary_bytes = zf.read(summary_name)
            lineage_bytes = zf.read(lineage_name)
        rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
        summary = json.loads(summary_bytes)
        lineage = json.loads(lineage_bytes)
        if not rows:
            raise ValueError("terminal CSV is empty")
        if len(rows) != int(summary.get("candidate_count", -1)) or len(rows) != int(summary.get("terminalized_count", -1)):
            raise ValueError("candidate count mismatch")
        if int(summary.get("research_limbo_count", -1)) != 0:
            raise ValueError("research limbo is nonzero")
        if summary.get("canonical_authority_unchanged") is not True or summary.get("hard_gate_unknown_is_pass") is not False or summary.get("no_auto_trade") is not True:
            raise ValueError("terminal summary authority invariant violated")
        if lineage.get("formal_authority_unchanged") is not True or lineage.get("no_auto_trade") is not True:
            raise ValueError("terminal lineage authority invariant violated")
        if not _manifest_matches_metadata(run, lineage):
            raise ValueError("terminal lineage manifest does not match producing run metadata")
        required = {"code", "terminal_decision", "decision_authority", "no_auto_trade", "terminal_policy_version"}
        if not required.issubset(set(rows[0])):
            raise ValueError("terminal CSV schema incomplete")
        if any(row.get("terminal_decision") not in {"BUY", "WAIT_PRICE", "REJECT"} for row in rows):
            raise ValueError("non-terminal decision found")
        if any(row.get("decision_authority") != "RESEARCH_TERMINAL_VIEW" for row in rows):
            raise ValueError("decision authority mismatch")
        if any(str(row.get("no_auto_trade")) != "True" for row in rows):
            raise ValueError("no_auto_trade mismatch")
        key = _manifest_lineage_key(lineage)
        if not key:
            raise ValueError("lineage key missing")
        return ArtifactValidation(
            valid=True,
            lineage_key=key,
            candidate_identity=_candidate_identity(rows),
            files={
                "candidate_terminal_decisions.csv": csv_bytes,
                "candidate_terminal_summary.json": summary_bytes,
                "terminal_lineage.json": lineage_bytes,
            },
        )
    except Exception as exc:
        return ArtifactValidation(valid=False, reason=f"artifact_invalid:{type(exc).__name__}:{exc}")


class GithubLoader:
    def __init__(self, repo: str, requested_run_id: str, root: Path):
        self.repo = repo
        self.requested_run_id = str(requested_run_id)
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs: dict[str, dict[str, Any]] = {}
        self.nodes: dict[str, TerminalProducerNode] = {}
        self.validated: dict[str, ArtifactValidation] = {}
        self.logs: list[str] = []

    def run(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.runs:
            self.runs[run_id] = _gh_json(self.repo, f"actions/runs/{run_id}")
        return self.runs[run_id]

    def _terminal_job(self, run_id: str) -> tuple[str, str]:
        jobs = _gh_json(self.repo, f"actions/runs/{run_id}/jobs?filter=latest&per_page=100").get("jobs", [])
        terminal = [job for job in jobs if job.get("name") == "terminalize"]
        if len(terminal) != 1:
            return "AMBIGUOUS", "AMBIGUOUS"
        return str(terminal[0].get("status") or ""), str(terminal[0].get("conclusion") or "")

    def _artifacts(self, run_id: str) -> list[dict[str, Any]]:
        artifacts = _gh_json(self.repo, f"actions/runs/{run_id}/artifacts?per_page=100").get("artifacts", [])
        return [a for a in artifacts if a.get("name") == ARTIFACT_NAME and a.get("expired") is False]

    def _validate_artifact(self, run_id: str, run: dict[str, Any], artifacts: list[dict[str, Any]]) -> ArtifactValidation:
        if len(artifacts) != 1:
            return ArtifactValidation(valid=False, reason=f"artifact_count={len(artifacts)}")
        artifact_id = str(artifacts[0].get("id") or "")
        if not artifact_id.isdigit():
            return ArtifactValidation(valid=False, reason="artifact_id_invalid")
        payload = _gh_bytes(self.repo, f"actions/artifacts/{artifact_id}/zip")
        validation = _validate_artifact_bytes(run, payload)
        if validation.valid:
            self.validated[run_id] = validation
        return validation

    def _base_node(self, run_id: str, expected_lineage: str = "") -> TerminalProducerNode:
        run = self.run(run_id)
        name = str(run.get("name") or "")
        branch = str(run.get("head_branch") or "")
        if not name.startswith(WORKFLOW_NAME) or branch != "main":
            raise LineageResolutionError(f"run {run_id} is not a main Candidate Terminal Review run")
        terminal_status, terminal_conclusion = self._terminal_job(run_id)
        artifacts = self._artifacts(run_id)
        validation = self._validate_artifact(run_id, run, artifacts) if len(artifacts) == 1 else ArtifactValidation(False, reason=f"artifact_count={len(artifacts)}")
        lineage_key = validation.lineage_key if validation.valid else expected_lineage
        return TerminalProducerNode(
            run_id=run_id,
            lineage_key=lineage_key,
            wrapper_status=str(run.get("status") or ""),
            wrapper_conclusion=str(run.get("conclusion") or ""),
            terminal_status=terminal_status,
            terminal_conclusion=terminal_conclusion,
            artifact_count=len(artifacts),
            artifact_valid=validation.valid,
            artifact_lineage_key=validation.lineage_key,
            artifact_candidate_identity=validation.candidate_identity,
            rejection_reason=validation.reason,
        )

    def _expected_lineage(self, current: TerminalProducerNode) -> str:
        if current.artifact_valid:
            return current.artifact_lineage_key
        run = self.run(current.run_id)
        candidates = _metadata_lineage_candidates(run)
        if len(candidates) == 1:
            return next(iter(candidates))
        return ""

    @staticmethod
    def _matches_expected(expected: str, run: dict[str, Any], validation: ArtifactValidation) -> bool:
        if not validation.valid:
            return False
        if expected:
            return validation.lineage_key == expected
        suffix = _suffix_run_id(run)
        if not suffix or str(run.get("event") or "") != "workflow_dispatch":
            return False
        if validation.lineage_key == f"POSTSCAN:{suffix}":
            return True
        return validation.lineage_key.startswith("EVERY_INDUSTRY_AUTHORIZED:") and validation.lineage_key.endswith(f":{suffix}")

    def build_chain(self) -> tuple[str, dict[str, TerminalProducerNode]]:
        requested = self.requested_run_id
        current = self._base_node(requested)
        run = self.run(requested)
        if str(run.get("event") or "") == "push":
            raise LineageResolutionError("push smoke Candidate Terminal runs are not production Recall producers")
        expected = self._expected_lineage(current)
        if current.artifact_valid:
            self.nodes[requested] = current
            return current.lineage_key, self.nodes

        if current.terminal_conclusion not in {"skipped", "success"}:
            raise LineageResolutionError(
                f"requested run {requested} terminalize={current.terminal_conclusion}; fallback forbidden"
            )

        requested_created = str(run.get("created_at") or "")
        listing = _gh_json(
            self.repo,
            f"actions/workflows/{WORKFLOW_FILE}/runs?branch=main&status=success&per_page={MAX_INSPECTED_RUNS}",
        ).get("workflow_runs", [])

        exact_nodes: list[TerminalProducerNode] = []
        exact_keys: set[str] = set()
        visited: set[str] = {requested}
        inspected = 0
        for item in listing:
            candidate = str(item.get("id") or "")
            if not candidate.isdigit() or candidate == requested or candidate in visited:
                continue
            if requested_created and str(item.get("created_at") or "") > requested_created:
                continue
            visited.add(candidate)
            inspected += 1
            if inspected > MAX_INSPECTED_RUNS:
                break
            candidate_run = self.run(candidate)
            terminal_status, terminal_conclusion = self._terminal_job(candidate)
            artifacts = self._artifacts(candidate)
            validation = self._validate_artifact(candidate, candidate_run, artifacts) if len(artifacts) == 1 else ArtifactValidation(False, reason=f"artifact_count={len(artifacts)}")
            if not validation.valid:
                self.logs.append(f"inspected run={candidate} rejected={validation.reason}")
                continue
            if not self._matches_expected(expected, candidate_run, validation):
                self.logs.append(f"inspected run={candidate} rejected=lineage_mismatch actual={validation.lineage_key}")
                continue
            if terminal_status != "completed" or terminal_conclusion != "success":
                self.logs.append(f"inspected run={candidate} rejected=terminal={terminal_status}/{terminal_conclusion}")
                continue
            exact_keys.add(validation.lineage_key)
            exact_nodes.append(
                TerminalProducerNode(
                    run_id=candidate,
                    lineage_key=validation.lineage_key,
                    wrapper_status=str(candidate_run.get("status") or ""),
                    wrapper_conclusion=str(candidate_run.get("conclusion") or ""),
                    terminal_status=terminal_status,
                    terminal_conclusion=terminal_conclusion,
                    artifact_count=len(artifacts),
                    artifact_valid=True,
                    artifact_lineage_key=validation.lineage_key,
                    artifact_candidate_identity=validation.candidate_identity,
                )
            )
            if len(exact_nodes) >= MAX_LINEAGE_HOPS:
                break

        if not expected:
            if len(exact_keys) > 1:
                raise LineageResolutionError(
                    f"workflow_dispatch lineage is ambiguous across exact suffix families: {sorted(exact_keys)}"
                )
            if exact_keys:
                expected = next(iter(exact_keys))
        if not expected:
            raise LineageResolutionError(
                f"run {requested} has no auditable exact lineage identity; stale/global fallback forbidden"
            )

        exact_nodes = [node for node in exact_nodes if node.lineage_key == expected]
        predecessor = exact_nodes[0].run_id if exact_nodes else None
        self.nodes[requested] = TerminalProducerNode(
            **{**current.__dict__, "lineage_key": expected, "predecessor_run_id": predecessor}
        )
        for index, node in enumerate(exact_nodes):
            next_id = exact_nodes[index + 1].run_id if index + 1 < len(exact_nodes) else None
            self.nodes[node.run_id] = TerminalProducerNode(
                **{**node.__dict__, "predecessor_run_id": next_id}
            )
        return expected, self.nodes

    def load_node(self, run_id: str) -> TerminalProducerNode:
        return self.nodes[run_id]

    def materialize_selected(self, run_id: str, output_dir: Path) -> None:
        validation = self.validated[run_id]
        assert validation.files
        selected = output_dir / "selected"
        selected.mkdir(parents=True, exist_ok=True)
        for name, payload in validation.files.items():
            (selected / name).write_bytes(payload)


def _append(path: str | None, lines: list[str]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as stream:
        for line in lines:
            stream.write(line + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--requested-run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--github-env", default=os.environ.get("GITHUB_ENV", ""))
    parser.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    parser.add_argument("--step-summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        loader = GithubLoader(args.repo, args.requested_run_id, args.output_dir)
        expected, _ = loader.build_chain()
        result = resolve_terminal_producer(
            args.requested_run_id,
            loader.load_node,
            max_hops=MAX_LINEAGE_HOPS,
        )
    except (LineageResolutionError, ValueError, subprocess.CalledProcessError) as exc:
        payload = {
            "status": "BLOCKED",
            "requested_run_id": str(args.requested_run_id),
            "error": str(exc),
            "stale_global_fallback_allowed": False,
        }
        (args.output_dir / "resolution.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    payload = {
        "status": result.status,
        "requested_run_id": result.requested_run_id,
        "selected_run_id": result.selected_run_id,
        "lineage_key": expected,
        "visited_run_ids": list(result.visited_run_ids),
        "resolver_log": [*loader.logs, *result.log],
        "stale_global_fallback_allowed": False,
        "max_lineage_hops": MAX_LINEAGE_HOPS,
        "max_inspected_runs": MAX_INSPECTED_RUNS,
    }
    (args.output_dir / "resolution.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    env_lines = [
        f"TERMINAL_RESOLUTION_STATUS={result.status}",
        f"TERMINAL_REQUESTED_RUN_ID={result.requested_run_id}",
        f"TERMINAL_LINEAGE_KEY={expected}",
    ]
    out_lines = [
        f"status={result.status}",
        f"requested_run_id={result.requested_run_id}",
        f"lineage_key={expected}",
    ]
    if result.status == "SELECTED" and result.selected_run_id:
        loader.materialize_selected(result.selected_run_id, args.output_dir)
        csv_path = args.output_dir / "selected" / "candidate_terminal_decisions.csv"
        env_lines += [
            f"TERMINAL_RUN_ID={result.selected_run_id}",
            f"TERMINAL_CSV={csv_path}",
            f"TERMINAL_FALLBACK_USED={'true' if result.selected_run_id != result.requested_run_id else 'false'}",
        ]
        out_lines += [
            f"selected_run_id={result.selected_run_id}",
            f"fallback_used={'true' if result.selected_run_id != result.requested_run_id else 'false'}",
        ]
    else:
        env_lines += ["TERMINAL_RUN_ID=", "TERMINAL_CSV=", "TERMINAL_FALLBACK_USED=false"]
        out_lines += ["selected_run_id=", "fallback_used=false"]

    _append(args.github_env, env_lines)
    _append(args.github_output, out_lines)
    _append(
        args.step_summary,
        [
            "### Exact Candidate Terminal producer resolution",
            f"- requested run: {result.requested_run_id}",
            f"- status: {result.status}",
            f"- exact lineage: `{expected}`",
            f"- selected producer: {result.selected_run_id or 'none'}",
            f"- visited: {', '.join(result.visited_run_ids)}",
            "- chronological/global stale fallback: forbidden",
            *[f"- {line}" for line in [*loader.logs, *result.log]],
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
