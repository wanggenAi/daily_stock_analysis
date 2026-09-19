#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "AGENTS.md"
CLAUDE = ROOT / "CLAUDE.md"
COPILOT = ROOT / ".github" / "copilot-instructions.md"
TASK_STATE = ROOT / "TASK_STATE.md"
RECOVERY_DOC = ROOT / "docs" / "WEB_SESSION_RECOVERY.md"
RECOVERY_EXAMPLE = ROOT / ".github" / "recovery" / "TASK_CHECKPOINT.example.json"
RECOVERY_VALIDATOR = ROOT / "scripts" / "validate_recovery_state.py"
INSTRUCTIONS_DIR = ROOT / ".github" / "instructions"
CLAUDE_SKILLS_DIR = ROOT / ".claude" / "skills"
RECOVERY_IGNORED_BUSINESS_WORKFLOWS = (
    ROOT / ".github" / "workflows" / "genge-opportunity-discovery.yml",
    ROOT / ".github" / "workflows" / "genge-risk-capped-opportunity-discovery.yml",
)
RECOVERY_ONLY_PATHS = (
    "AGENTS.md",
    "docs/WEB_SESSION_RECOVERY.md",
    "scripts/check_ai_assets.py",
    "scripts/validate_recovery_state.py",
    ".github/recovery/**",
)

REQUIRED_INSTRUCTION_FILES = {
    "backend.instructions.md",
    "client.instructions.md",
    "governance.instructions.md",
}

REQUIRED_SKILL_FILES = {
    "README.md",
    "analyze-issue/SKILL.md",
    "analyze-pr/SKILL.md",
    "fix-issue/SKILL.md",
}

REQUIRED_GITIGNORE_SNIPPETS = (
    ".claude/*",
    "!.claude/skills/",
    "!.claude/skills/**",
)

REQUIRED_TASK_STATE_HEADINGS = (
    "# Current Mission",
    "## Goal",
    "## Current Phase",
    "## Last Verified Main",
    "## Active Branch",
    "## Active PR",
    "## CI",
    "## Production / Artifact",
    "## Completed",
    "## Current Findings",
    "## Blockers",
    "## Next Action",
    "## Do Not Repeat",
    "## Guardrails",
)



def fail(message: str) -> None:
    print(f"[ai-assets] ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def ensure_file_exists(path: Path, description: str) -> None:
    if not path.exists():
        fail(f"{description} is missing: {path.relative_to(ROOT)}")


def ensure_symlink() -> None:
    ensure_file_exists(AGENTS, "canonical AGENTS.md")
    if not CLAUDE.exists():
        fail("CLAUDE.md is missing")
    if not CLAUDE.is_symlink():
        fail("CLAUDE.md must be a symlink to AGENTS.md")

    target = Path(CLAUDE.readlink())
    if target != Path("AGENTS.md"):
        fail(f"CLAUDE.md must point to AGENTS.md, found: {target}")


def ensure_copilot_entry() -> None:
    ensure_file_exists(COPILOT, "repository Copilot instructions")
    content = COPILOT.read_text(encoding="utf-8")
    required_fragments = (
        "Canonical source:",
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/skills/",
    )
    for fragment in required_fragments:
        if fragment not in content:
            fail(f".github/copilot-instructions.md is missing required text: {fragment!r}")


def ensure_task_state() -> None:
    ensure_file_exists(TASK_STATE, "resumable task state")
    content = TASK_STATE.read_text(encoding="utf-8")
    lines = content.splitlines()
    if len(lines) > 120:
        fail("TASK_STATE.md must stay concise (maximum 120 lines)")
    for heading in REQUIRED_TASK_STATE_HEADINGS:
        if heading not in lines:
            fail(f"TASK_STATE.md is missing required heading: {heading!r}")



def ensure_recovery_protocol() -> None:
    ensure_file_exists(RECOVERY_DOC, "web-session recovery protocol")
    ensure_file_exists(RECOVERY_EXAMPLE, "recovery state schema example")
    ensure_file_exists(RECOVERY_VALIDATOR, "recovery state validator")
    agents = AGENTS.read_text(encoding="utf-8")
    protocol = RECOVERY_DOC.read_text(encoding="utf-8")

    required_agent_fragments = (
        "## Durable web-session checkpoint branch — LOCKED",
        "recovery/tasks/<task_key>.json",
        "live GitHub refs/PRs/Actions/artifacts/persisted data > recovery checkpoint",
        "Runtime latency tax must remain zero",
        "[skip ci] recovery:",
        "pending_operation",
    )
    for fragment in required_agent_fragments:
        if fragment not in agents:
            fail(f"AGENTS.md is missing recovery contract text: {fragment!r}")

    required_protocol_fragments = (
        "## Adaptive checkpoint sizing",
        "## Task-scoped concurrency",
        "## Non-interference invariant — zero business-runtime tax",
        "## Fenced single-writer and compare-and-swap",
        "## Write-ahead intent and ambiguous outcomes",
        "## Idempotent recovery rules",
        "## Atomic checkpoint procedure",
        "## State bounds, integrity and secret hygiene",
        "## Degraded recovery mode",
        "## Resume algorithm",
        "## Crash-window rule",
        "maximum serialized size: 16 KiB",
        "recovery-only PR",
    )
    for fragment in required_protocol_fragments:
        if fragment not in protocol:
            fail(f"docs/WEB_SESSION_RECOVERY.md is missing required text: {fragment!r}")

    result = subprocess.run(
        [sys.executable, str(RECOVERY_VALIDATOR), str(RECOVERY_EXAMPLE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fail(result.stderr.strip() or result.stdout.strip() or "recovery-state validation failed")

    isolation = subprocess.run(
        [
            "git", "grep", "-l",
            "-e", "RECOVERY_STATE.json",
            "-e", "state/chatgpt-recovery",
            "--", "main.py", "src", "api", "bot", "data_provider", "apps", ".github/workflows",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if isolation.returncode not in (0, 1):
        fail(isolation.stderr.strip() or "git grep failed while checking recovery isolation")
    matches = [line.strip() for line in isolation.stdout.splitlines() if line.strip()]
    if matches:
        fail("recovery leaked into business/runtime paths: " + ", ".join(matches))


def ensure_recovery_workflow_isolation() -> None:
    for workflow in RECOVERY_IGNORED_BUSINESS_WORKFLOWS:
        ensure_file_exists(workflow, "business workflow")
        text = workflow.read_text(encoding="utf-8")
        if "paths-ignore:" not in text:
            fail(f"{workflow.relative_to(ROOT)} must exclude recovery-only PR paths")
        for recovery_path in RECOVERY_ONLY_PATHS:
            if recovery_path not in text:
                fail(
                    f"{workflow.relative_to(ROOT)} is missing recovery-only path exclusion: "
                    f"{recovery_path!r}"
                )


def ensure_instruction_files() -> None:
    ensure_file_exists(INSTRUCTIONS_DIR, "instructions directory")
    actual = {path.name for path in INSTRUCTIONS_DIR.glob("*.instructions.md")}
    missing = REQUIRED_INSTRUCTION_FILES - actual
    if missing:
        fail(f"missing instruction files: {', '.join(sorted(missing))}")


def ensure_skill_files() -> None:
    ensure_file_exists(CLAUDE_SKILLS_DIR, "Claude skills directory")
    for relative_path in REQUIRED_SKILL_FILES:
        path = CLAUDE_SKILLS_DIR / relative_path
        if not path.exists():
            fail(f"missing repository skill asset: {path.relative_to(ROOT)}")
        if path.is_file():
            content = path.read_text(encoding="utf-8")
            if relative_path != "README.md" and "AGENTS.md" not in content:
                fail(f"{path.relative_to(ROOT)} must reference AGENTS.md as the rule source")


def ensure_gitignore_rules() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for snippet in REQUIRED_GITIGNORE_SNIPPETS:
        if snippet not in gitignore:
            fail(f".gitignore is missing required AI asset rule: {snippet}")


def ensure_no_tracked_claude_artifacts() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--", ".claude"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    allowed_prefixes = (".claude/skills/",)
    for path in tracked:
        if path.startswith(allowed_prefixes):
            continue
        fail(f"tracked .claude artifact outside skills/: {path}")


def main() -> None:
    ensure_symlink()
    ensure_copilot_entry()
    ensure_task_state()
    ensure_recovery_protocol()
    ensure_recovery_workflow_isolation()
    ensure_instruction_files()
    ensure_skill_files()
    ensure_gitignore_rules()
    ensure_no_tracked_claude_artifacts()
    print("[ai-assets] OK")


if __name__ == "__main__":
    main()
