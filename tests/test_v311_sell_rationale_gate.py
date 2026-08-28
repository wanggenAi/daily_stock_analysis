import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.holding_valuation_continuity import (
    sell_review_required,
)


def _write_state(path: Path, *, neutral=100.0, normalized=10.0, action="HOLD"):
    path.write_text(
        json.dumps(
            {
                "contract_version": "V311_HOLDING_SELL_RATIONALE_V3",
                "holdings": {
                    "600000": {
                        "action": action,
                        "neutral_value": neutral,
                        "normalized_earnings": normalized,
                        "current_price": 100.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _row(**overrides):
    row = {
        "code": "600000",
        "v311_has_position": True,
        "v31_current_price": 130.0,
        "v31_neutral_value": 100.0,
        "v31_normalized_profit": 10.0,
    }
    row.update(overrides)
    return row


def test_missing_baseline_blocks_formal_sell(tmp_path):
    state = tmp_path / "state.json"
    required, reasons = sell_review_required(_row(), "REDUCE_25", path=state)
    assert required is True
    assert "SELL_RATIONALE_BASELINE_MISSING" in reasons


def test_stable_value_and_material_overextension_allows_sell(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state)
    required, reasons = sell_review_required(_row(v31_current_price=125.0), "REDUCE_25", path=state)
    assert required is False
    assert reasons == ("SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION",)


def test_stable_value_but_small_overvaluation_blocks_sell(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state)
    required, reasons = sell_review_required(_row(v31_current_price=110.0), "REDUCE_25", path=state)
    assert required is True
    assert "SELL_RATIONALE_NOT_MATERIAL" in reasons


def test_neutral_value_jump_without_material_evidence_blocks_sell(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state, neutral=100.0)
    required, reasons = sell_review_required(
        _row(v31_neutral_value=70.0, v31_current_price=120.0),
        "REDUCE_50",
        path=state,
    )
    assert required is True
    assert "NEUTRAL_VALUE_DISCONTINUITY" in reasons
    assert "SELL_RATIONALE_NOT_PROVEN" in reasons


def test_thin_free_text_cannot_override_discontinuity(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state, neutral=100.0)
    required, reasons = sell_review_required(
        _row(
            v31_neutral_value=70.0,
            valuation_continuity_evidence_id="e1",
            valuation_continuity_evidence_observed_at="2026-08-28T00:00:00Z",
            valuation_continuity_evidence_reason="valuation lower",
            valuation_continuity_evidence_type="VALUATION_MODEL_INPUT_CORRECTION",
            valuation_continuity_evidence_material=True,
            valuation_continuity_thesis_link="normalized earnings basis corrected",
        ),
        "REDUCE_50",
        path=state,
    )
    assert required is True
    assert "SELL_EVIDENCE_REASON_TOO_THIN" in reasons


def test_material_thesis_linked_evidence_can_override_discontinuity(tmp_path):
    state = tmp_path / "state.json"
    _write_state(state, neutral=100.0)
    required, reasons = sell_review_required(
        _row(
            v31_neutral_value=70.0,
            valuation_continuity_evidence_id="filing-2026q2-guidance-cut",
            valuation_continuity_evidence_observed_at="2026-08-28T00:00:00Z",
            valuation_continuity_evidence_reason=(
                "Management materially cut full-year earnings guidance and the new filing "
                "shows the prior normalized earnings assumption is no longer supportable."
            ),
            valuation_continuity_evidence_type="GUIDANCE_CUT",
            valuation_continuity_evidence_material=True,
            valuation_continuity_thesis_link=(
                "The original holding thesis depended on durable earnings growth; the cut "
                "directly invalidates that assumption."
            ),
        ),
        "REDUCE_50",
        path=state,
    )
    assert required is False
    assert reasons == ("SELL_RATIONALE_MATERIAL_REUNDERWRITE_EVIDENCE",)


def test_non_sell_action_is_not_intercepted(tmp_path):
    state = tmp_path / "state.json"
    required, reasons = sell_review_required(_row(), "HOLD", path=state)
    assert required is False
    assert reasons == ()
