"""Run the GitHub-hosted Jev shadow evaluation for the GenGe stock system."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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
        "--scope",
        choices=("holdings", "unresolved", "combined"),
        default="combined",
    )
    parser.add_argument("--max-entities", type=int, default=25)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
