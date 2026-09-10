from src.strategies.genge_opportunity_discovery.all_a_progress_runner import _apply_user_trade_universe
from src.strategies.genge_opportunity_discovery.user_trade_universe import (
    is_user_tradable_a_share,
    normalize_security_code,
    trade_universe_rejection_reason,
)


def test_user_trade_universe_accepts_shanghai_and_shenzhen_main_board_a_shares():
    accepted = [
        "600519",
        "601899.SH",
        "SH603993",
        "605060.SH",
        "000001",
        "001316.SZ",
        "SZ002594",
        "003816",
    ]
    assert all(is_user_tradable_a_share(code) for code in accepted)


def test_user_trade_universe_rejects_chinext_star_and_other_non_executable_products():
    rejected = [
        "300693.SZ",  # ChiNext / 创业板
        "301589.SZ",  # ChiNext / 创业板
        "688019.SH",  # STAR / 科创板
        "689009.SH",  # STAR-family prefix
        "920001.BJ",
        "BJ830001",
        "430001",
        "510300.SH",  # Shanghai ETF
        "159915.SZ",  # Shenzhen ETF
        "900901.SH",  # Shanghai B share
        "200002.SZ",  # Shenzhen B share
        "00700.HK",
        "AAPL",
        "US.AAPL",
        "",
    ]
    assert all(not is_user_tradable_a_share(code) for code in rejected)


def test_explicit_market_must_match_code_family():
    assert not is_user_tradable_a_share("600519.SZ")
    assert not is_user_tradable_a_share("SZ600519")
    assert not is_user_tradable_a_share("000001.SH")
    assert not is_user_tradable_a_share("SH000001")


def test_normalize_security_code_is_conservative():
    assert normalize_security_code("SH600519") == "600519"
    assert normalize_security_code("300693.SZ") == "300693"
    assert normalize_security_code("688019.SH") == "688019"
    assert normalize_security_code("600519.SZ") == "600519"
    assert normalize_security_code("00700.HK") == ""
    assert normalize_security_code("AAPL") == ""


def test_all_a_runner_marks_out_of_scope_rows_before_quant_screen():
    rows = [
        {"code": "600519", "exclusion_reason": ""},
        {"code": "001316.SZ", "exclusion_reason": ""},
        {"code": "300693.SZ", "exclusion_reason": ""},
        {"code": "688019.SH", "exclusion_reason": ""},
        {"code": "920001.BJ", "exclusion_reason": ""},
        {"code": "510300.SH", "exclusion_reason": ""},
    ]

    allowed, rejected = _apply_user_trade_universe(rows)

    assert (allowed, rejected) == (2, 4)
    assert rows[0]["user_trade_universe_eligible"] is True
    assert rows[1]["user_trade_universe_eligible"] is True
    for row in rows[2:]:
        assert row["user_trade_universe_eligible"] is False
        assert row["exclusion_reason"] == "USER_TRADE_UNIVERSE_SH_SZ_MAIN_A_ONLY"
    assert trade_universe_rejection_reason("300693.SZ") == "USER_TRADE_UNIVERSE_SH_SZ_MAIN_A_ONLY"
    assert trade_universe_rejection_reason("688019.SH") == "USER_TRADE_UNIVERSE_SH_SZ_MAIN_A_ONLY"


def test_trade_universe_does_not_overwrite_stronger_existing_exclusion_reason():
    rows = [{"code": "300693.SZ", "exclusion_reason": "ST_OR_DELIST_RISK"}]
    _apply_user_trade_universe(rows)
    assert rows[0]["exclusion_reason"] == "ST_OR_DELIST_RISK"
    assert rows[0]["user_trade_universe_eligible"] is False
