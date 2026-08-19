"""Production adapter: strict Hard Logic Engine -> existing price valuation map.

The valuation machinery in ``hard_logic_price_map`` remains reusable, but its
legacy compatibility gate is intentionally replaced for this production path by
``hard_logic_engine.hard_logic_assessment``.  This prevents Quant ranking,
valuation readiness, or earnings quality alone from being promoted to HARD_LOGIC_PASS.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from . import hard_logic_price_map as price_map
from .hard_logic_engine import hard_logic_assessment


@contextmanager
def _strict_gate_installed() -> Iterator[None]:
    original = price_map.hard_logic_assessment
    price_map.hard_logic_assessment = hard_logic_assessment
    try:
        yield
    finally:
        price_map.hard_logic_assessment = original


def build_strict_price_expectation_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    with _strict_gate_installed():
        return price_map.build_price_expectation_rows(rows)


def write_price_map(artifact_root: Path, output_dir: Path) -> list[dict[str, Any]]:
    with _strict_gate_installed():
        return price_map.write_price_map(artifact_root, output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_price_map(args.artifact_root, args.output_dir)
    print(f"strict_hard_logic_price_map={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
