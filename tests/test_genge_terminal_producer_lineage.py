from __future__ import annotations

import pytest

from src.strategies.genge_opportunity_discovery.terminal_producer_lineage import (
    LineageResolutionError,
    TerminalProducerNode,
    resolve_terminal_producer,
)


def _loader(nodes: dict[str, TerminalProducerNode]):
    return lambda run_id: nodes[run_id]


def _node(
    run_id: int,
    *,
    pred: int | None = None,
    terminal: str = "success",
    count: int = 1,
    valid: bool = True,
    lineage: str = "L:42",
    artifact_lineage: str = "L:42",
    identity: str = "codes:abc",
    reason: str = "",
) -> TerminalProducerNode:
    return TerminalProducerNode(
        run_id=str(run_id),
        lineage_key=lineage,
        predecessor_run_id=None if pred is None else str(pred),
        terminal_status="completed",
        terminal_conclusion=terminal,
        artifact_count=count,
        artifact_valid=valid,
        artifact_lineage_key=artifact_lineage,
        artifact_candidate_identity=identity,
        rejection_reason=reason,
    )


def test_case_a_skipped_wrapper_falls_back_to_exact_valid_ancestor() -> None:
    result = resolve_terminal_producer(
        "3",
        _loader(
            {
                "3": _node(3, pred=2, terminal="skipped", count=0, identity=""),
                "2": _node(2),
            }
        ),
    )
    assert result.status == "SELECTED"
    assert result.selected_run_id == "2"
    assert result.visited_run_ids == ("3", "2")


def test_case_b_nearest_valid_producer_is_used_directly() -> None:
    result = resolve_terminal_producer("3", _loader({"3": _node(3, pred=2), "2": _node(2)}))
    assert result.selected_run_id == "3"
    assert result.visited_run_ids == ("3",)


def test_case_c_successful_job_missing_artifact_continues_predecessor() -> None:
    result = resolve_terminal_producer(
        "3",
        _loader({"3": _node(3, pred=2, count=0, identity=""), "2": _node(2)}),
    )
    assert result.selected_run_id == "2"
    assert any("artifact_count=0" in line for line in result.log)


def test_case_d_artifact_lineage_mismatch_is_rejected_without_cross_lineage_consumption() -> None:
    result = resolve_terminal_producer(
        "3",
        _loader({"3": _node(3, pred=2, artifact_lineage="OTHER"), "2": _node(2)}),
    )
    assert result.selected_run_id == "2"
    assert any("artifact_lineage_mismatch" in line for line in result.log)


def test_case_e_entire_lineage_without_producer_is_not_found() -> None:
    result = resolve_terminal_producer(
        "3",
        _loader(
            {
                "3": _node(3, pred=2, terminal="skipped", count=0, identity=""),
                "2": _node(2, terminal="skipped", count=0, identity=""),
            }
        ),
    )
    assert result.status == "NOT_FOUND"
    assert result.selected_run_id is None


def test_case_f_cycle_fails_closed() -> None:
    with pytest.raises(LineageResolutionError, match="cycle"):
        resolve_terminal_producer(
            "3",
            _loader(
                {
                    "3": _node(3, pred=2, terminal="skipped", count=0, identity=""),
                    "2": _node(2, pred=3, terminal="skipped", count=0, identity=""),
                }
            ),
        )


def test_case_f_hop_limit_fails_closed() -> None:
    nodes = {
        str(i): _node(i, pred=i - 1, terminal="skipped", count=0, identity="")
        for i in range(2, 8)
    }
    nodes["1"] = _node(1)
    with pytest.raises(LineageResolutionError, match="max_hops"):
        resolve_terminal_producer("7", _loader(nodes), max_hops=3)


def test_case_g_normal_success_path_is_unchanged() -> None:
    result = resolve_terminal_producer("9", _loader({"9": _node(9, identity="codes:normal")}))
    assert result.status == "SELECTED"
    assert result.lineage_key == "L:42"


def test_predecessor_node_lineage_mismatch_fails_closed_instead_of_crossing_generation() -> None:
    nodes = {
        "3": _node(
            3,
            pred=2,
            terminal="skipped",
            count=0,
            identity="",
            lineage="L:42",
            artifact_lineage="L:42",
        ),
        "2": _node(2, lineage="L:99", artifact_lineage="L:99"),
    }
    with pytest.raises(LineageResolutionError, match="crossed lineage"):
        resolve_terminal_producer("3", _loader(nodes))
