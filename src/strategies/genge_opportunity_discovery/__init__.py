"""Daily research opportunity discovery for GenGe Cycle Bottom.

Keep package import lightweight so production authority/provenance utilities can
run in minimal persistence jobs without importing the full pandas-backed discovery
pipeline. The public ``run_opportunity_discovery`` symbol remains lazily available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pipeline import run_opportunity_discovery as run_opportunity_discovery

__all__ = ["run_opportunity_discovery"]


def __getattr__(name: str) -> Any:
    if name == "run_opportunity_discovery":
        from .pipeline import run_opportunity_discovery

        globals()[name] = run_opportunity_discovery
        return run_opportunity_discovery
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
