from pathlib import Path


def test_research_priority_must_not_treat_closed_positions_as_current_holdings() -> None:
    holdings = Path('CURRENT_HOLDINGS.md').read_text(encoding='utf-8')
    priority = Path('data/research_priority/latest.json').read_text(encoding='utf-8')

    assert '603369 | 今世缘' in holdings and '| CLOSED |' in holdings
    assert '600276 | 恒瑞医药' in holdings and '| CLOSED |' in holdings

    # Durable research-priority state must never project a closed manual position
    # back into CURRENT_HOLDING. Historical/candidate presence is allowed; the
    # current-holding reason code is not.
    for code in ('603369', '600276'):
        marker = f'"code": "{code}"'
        if marker not in priority:
            continue
        block = priority.split(marker, 1)[1].split('\n    },', 1)[0]
        assert '"CURRENT_HOLDING"' not in block
