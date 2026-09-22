"""Run the GitHub-hosted Jev shadow evaluation for the GenGe stock system."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Direct script execution puts tools/ rather than the repository root on
# sys.path. Add the root explicitly so GitHub Actions and local CLI execution
# resolve the in-repo src package deterministically.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.strategies.genge_opportunity_discovery.jev_shadow import (
    JevShadowConfig,
    build_stock_shadow_states,
    evaluate_stock_shadow,
    render_shadow_markdown,
)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=Path("data/investor_decision_dashboard/latest.json"),
    )
    parser.add_argument(
        "--deep-status",
        type=Path,
        default=Path("data/deep_calculation/latest_status.json"),
    )
    parser.add_argument(
        "--profiles",
        type=Path,
        default=Path("data/deep_calculation/latest_profiles.json"),
    )
    parser.add_argument(
        "--research-decisions",
        type=Path,
        default=Path("data/deep_calculation/latest_research_decisions.json"),
    )
    parser.add_argument(
        "--research-priority",
        type=Path,
        default=Path("data/research_priority/latest.json"),
    )
    parser.add_argument(
        "--scope",
        choices=("holdings", "unresolved", "combined"),
        default="combined",
    )
    parser.add_argument("--max-entities", type=int, default=25)
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="Return non-zero unless the live Jev execution status is SUCCESS.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/jev-shadow"),
    )
    args = parser.parse_args()

    states = build_stock_shadow_states(
        dashboard=_read_json(args.dashboard),
        deep_status=_read_json(args.deep_status),
        profiles=_read_json(args.profiles),
        research_decisions=_read_json(args.research_decisions),
        research_priority=_read_json(args.research_priority),
        scope=args.scope,
        max_entities=args.max_entities,
    )
    payload = evaluate_stock_shadow(
        states=states,
        config=JevShadowConfig.from_env(),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "jev_shadow.json"
    md_path = args.output_dir / "jev_shadow.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_shadow_markdown(payload), encoding="utf-8")
    print(json.dumps(payload.get("summary") or {}, ensure_ascii=False, sort_keys=True))
    if args.require_success and payload.get("execution_status") != "SUCCESS":
        print(
            json.dumps(
                {"execution_status": payload.get("execution_status") or "UNKNOWN"},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
