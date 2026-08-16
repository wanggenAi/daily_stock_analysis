import pytest

from src.strategies.genge_opportunity_discovery.segment_cycle_blend import (
    blend_segment_cycle_earnings,
)


def test_mixed_business_keeps_stable_segment_and_normalizes_only_cyclical_segment():
    result = blend_segment_cycle_earnings(
        {
            "memory": {
                "forward_profit": 80.0,
                "is_cyclical": True,
                "through_cycle_ratio": 0.40,
            },
            "mcu_and_analog": {
                "forward_profit": 20.0,
                "is_cyclical": False,
            },
        }
    )

    assert result.forward_profit == pytest.approx(100.0)
    assert result.cyclical_forward_profit == pytest.approx(80.0)
    assert result.non_cyclical_forward_profit == pytest.approx(20.0)
    assert result.cycle_exposure_ratio == pytest.approx(0.80)
    assert result.through_cycle_normalized_profit == pytest.approx(52.0)
    assert result.peak_earnings_discount == pytest.approx(0.48)
    assert result.status == "OK"


def test_cyclical_segment_without_explicit_normalization_fails_closed():
    result = blend_segment_cycle_earnings(
        {
            "memory": {"forward_profit": 80.0, "is_cyclical": True},
            "mcu": {"forward_profit": 20.0, "is_cyclical": False},
        }
    )

    assert result.forward_profit == pytest.approx(100.0)
    assert result.through_cycle_normalized_profit is None
    assert result.peak_earnings_discount is None
    assert result.status == "SEGMENT_NORMALIZATION_INCOMPLETE"
    assert result.segments["memory"]["normalization_method"] == "CYCLE_NORMALIZATION_REQUIRED"


def test_non_cyclical_segment_can_use_explicit_normalized_profit():
    result = blend_segment_cycle_earnings(
        {
            "platform": {
                "forward_profit": 20.0,
                "through_cycle_profit": 18.0,
                "is_cyclical": False,
            }
        }
    )

    assert result.through_cycle_normalized_profit == pytest.approx(18.0)
    assert result.status == "OK"
