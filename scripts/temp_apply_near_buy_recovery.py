from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


script = Path("scripts/near_buy_research_overlay.py")
replace_once(
    script,
    'POLICY_VERSION = "near_buy_research_overlay_v1_observer_only"\nRESEARCH_AUTHORITY = "OBSERVER_ONLY_RESEARCH_OVERLAY"\nEVIDENCE_STATES = frozenset({"SUFFICIENT", "MISSING", "CONFLICTED", "CONFIRMED_NEGATIVE"})\nNEAR_BUY_STATE = "NEAR_BUY"\nNONE_STATE = "NONE"\n',
    'POLICY_VERSION = "near_buy_research_overlay_v2_evidence_recovery"\nRESEARCH_AUTHORITY = "OBSERVER_ONLY_RESEARCH_OVERLAY"\nEVIDENCE_STATES = frozenset({"SUFFICIENT", "MISSING", "CONFLICTED", "CONFIRMED_NEGATIVE"})\nNEAR_BUY_STATE = "NEAR_BUY"\nEVIDENCE_RECOVERY_STATE = "EVIDENCE_RECOVERY_PRIORITY"\nNONE_STATE = "NONE"\nRECOVERY_TIERS = ("A", "B", "C")\n',
)

classify_marker = "def classify_terminal_row(row: Mapping[str, Any], *, starter_fraction: float = STARTER_FRACTION) -> dict[str, Any]:\n"
helper = '''def _evidence_recovery_tier(
    row: Mapping[str, Any],
    *,
    state: str,
    hard_failures: Sequence[str],
    negatives: Sequence[str],
    conflicts: Sequence[str],
    exec_eligible: bool,
    retryable: bool,
    full_review: bool,
    terminal_decision: str,
) -> str | None:
    """Prioritize missing-only evidence recovery without creating trade authority."""
    if (
        terminal_decision != "REJECT"
        or state != "MISSING"
        or hard_failures
        or negatives
        or conflicts
        or not exec_eligible
        or not retryable
        or not full_review
    ):
        return None

    financial_ok = _text(row.get("financial_review_status")).upper() == "OK"
    valuation_ok = _text(row.get("valuation_diagnostic_status")).upper() == "OK"
    if not (financial_ok and valuation_ok):
        return None

    second_pass = _text(row.get("long_term_second_pass_status")).upper()
    quant_status = _text(row.get("quant_status")).upper()
    if second_pass == "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES":
        return "A"
    if quant_status == "PRIORITY_RESEARCH":
        return "B"
    if quant_status == "SECONDARY_RESEARCH":
        return "C"
    return None


'''
replace_once(script, classify_marker, helper + classify_marker)

replace_once(
    script,
    '''    reason_codes: list[str] = []
    if near_buy:
        reason_codes.append("high_research_score_without_confirmed_negative")
        if terminal_decision == "WAIT_PRICE":
            reason_codes.append("already_terminal_wait_price")
        if missing:
            reason_codes.append("missing_evidence_not_negative_evidence")
        if conflicts:
            reason_codes.append("conflicted_evidence_requires_resolution")

    result.update(
        {
            "research_opportunity_state": NEAR_BUY_STATE if near_buy else NONE_STATE,
            "near_buy_reason_codes": ";".join(reason_codes),
''',
    '''    recovery_tier = None if near_buy else _evidence_recovery_tier(
        row,
        state=state,
        hard_failures=hard_failures,
        negatives=negatives,
        conflicts=conflicts,
        exec_eligible=exec_eligible,
        retryable=retryable,
        full_review=full_review,
        terminal_decision=terminal_decision,
    )

    reason_codes: list[str] = []
    if near_buy:
        reason_codes.append("high_research_score_without_confirmed_negative")
        if terminal_decision == "WAIT_PRICE":
            reason_codes.append("already_terminal_wait_price")
        if missing:
            reason_codes.append("missing_evidence_not_negative_evidence")
        if conflicts:
            reason_codes.append("conflicted_evidence_requires_resolution")

    recovery_reason_codes: list[str] = []
    if recovery_tier:
        recovery_reason_codes.extend([
            "missing_evidence_requires_recovery",
            "financial_review_completed",
            "valuation_diagnostic_completed",
        ])
        if recovery_tier == "A":
            recovery_reason_codes.append("non_exit_profile_second_pass_completed")
        else:
            recovery_reason_codes.append(
                f"quant_research_priority:{_text(row.get('quant_status')).upper() or 'UNKNOWN'}"
            )

    if near_buy:
        opportunity_state = NEAR_BUY_STATE
    elif recovery_tier:
        opportunity_state = EVIDENCE_RECOVERY_STATE
    else:
        opportunity_state = NONE_STATE

    result.update(
        {
            "research_opportunity_state": opportunity_state,
            "near_buy_reason_codes": ";".join(reason_codes),
            "evidence_recovery_priority_tier": recovery_tier or "",
            "evidence_recovery_reason_codes": ";".join(recovery_reason_codes),
            "evidence_recovery_starter_allowed": False,
''',
)
replace_once(
    script,
    '''    if near_buy and (negatives or hard_failures):
        raise AssertionError("Near-BUY emitted despite confirmed negative/hard failure")
    return result
''',
    '''    if near_buy and (negatives or hard_failures):
        raise AssertionError("Near-BUY emitted despite confirmed negative/hard failure")
    if recovery_tier and (negatives or hard_failures or conflicts):
        raise AssertionError("evidence recovery emitted despite negative/conflicted evidence")
    if recovery_tier and result["starter_position_advisory_allowed"]:
        raise AssertionError("missing-evidence recovery must never receive starter advisory")
    return result
''',
)
replace_once(
    script,
    '''    projected.sort(
        key=lambda row: (
            0 if row["research_opportunity_state"] == NEAR_BUY_STATE else 1,
            -(_float(row.get("v31_score_total")) or -1.0),
            _float(row.get("master_research_rank")) or 10**9,
            _code(row.get("code")),
        )
    )
''',
    '''    tier_priority = {tier: index for index, tier in enumerate(RECOVERY_TIERS)}

    def sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
        state = _text(row.get("research_opportunity_state"))
        rank = _float(row.get("master_research_rank")) or 10**9
        code = _code(row.get("code"))
        if state == NEAR_BUY_STATE:
            return (0, 0, -(_float(row.get("v31_score_total")) or -1.0), rank, code)
        if state == EVIDENCE_RECOVERY_STATE:
            tier = _text(row.get("evidence_recovery_priority_tier"))
            return (1, tier_priority.get(tier, 99), 0.0, rank, code)
        return (2, 99, 0.0, rank, code)

    projected.sort(key=sort_key)
''',
)
replace_once(
    script,
    '''    evidence_counts = Counter(_text(row.get("near_buy_evidence_state")) for row in rows)
    near_buy_count = sum(row.get("research_opportunity_state") == NEAR_BUY_STATE for row in rows)
    return {
''',
    '''    evidence_counts = Counter(_text(row.get("near_buy_evidence_state")) for row in rows)
    near_buy_count = sum(row.get("research_opportunity_state") == NEAR_BUY_STATE for row in rows)
    recovery_rows = [row for row in rows if row.get("research_opportunity_state") == EVIDENCE_RECOVERY_STATE]
    recovery_tiers = Counter(_text(row.get("evidence_recovery_priority_tier")) for row in recovery_rows)
    return {
''',
)
replace_once(
    script,
    '''        "near_buy_count": near_buy_count,
        "evidence_state_counts": dict(sorted(evidence_counts.items())),
''',
    '''        "near_buy_count": near_buy_count,
        "evidence_recovery_count": len(recovery_rows),
        "evidence_recovery_tier_counts": {tier: recovery_tiers.get(tier, 0) for tier in RECOVERY_TIERS},
        "evidence_state_counts": dict(sorted(evidence_counts.items())),
''',
)
replace_once(
    script,
    '''        "confirmed_negative_can_be_near_buy": False,
        "automatic_promotion_allowed": False,
''',
    '''        "confirmed_negative_can_be_near_buy": False,
        "evidence_recovery_starter_allowed": False,
        "unknown_evidence_is_pass": False,
        "evidence_recovery_is_formal_signal": False,
        "automatic_promotion_allowed": False,
''',
)
replace_once(
    script,
    '''        "research_opportunity_state", "near_buy_evidence_state", "near_buy_reason_codes",
        "missing_evidence_items", "conflicted_evidence_items", "confirmed_negative_items",
''',
    '''        "research_opportunity_state", "near_buy_evidence_state", "near_buy_reason_codes",
        "evidence_recovery_priority_tier", "evidence_recovery_reason_codes",
        "missing_evidence_items", "conflicted_evidence_items", "confirmed_negative_items",
''',
)
replace_once(
    script,
    '''        "starter_position_advisory_allowed", "starter_fraction_of_normal_target",
        "starter_advisory_research_only", "formal_action_unchanged",
''',
    '''        "starter_position_advisory_allowed", "starter_fraction_of_normal_target",
        "evidence_recovery_starter_allowed", "starter_advisory_research_only", "formal_action_unchanged",
''',
)
replace_once(
    script,
    '''        f"- Near-BUY: {summary['near_buy_count']}",
        f"- starter advisory: {STARTER_FRACTION:.0%} of normal target when eligible",
        "",
    ]
''',
    '''        f"- Near-BUY: {summary['near_buy_count']}",
        f"- Evidence recovery priority: {summary['evidence_recovery_count']} "
        f"(A={summary['evidence_recovery_tier_counts']['A']}, "
        f"B={summary['evidence_recovery_tier_counts']['B']}, "
        f"C={summary['evidence_recovery_tier_counts']['C']})",
        f"- starter advisory: {STARTER_FRACTION:.0%} of normal target for Near-BUY only",
        "- missing-evidence recovery: no starter position; UNKNOWN remains non-PASS",
        "",
    ]
''',
)
replace_once(
    script,
    '''    (output_dir / "near_buy_research_overlay.md").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    return rows
''',
    '''    recovery_rows = [row for row in rows if row["research_opportunity_state"] == EVIDENCE_RECOVERY_STATE]
    if recovery_rows:
        lines.extend(["", "## Evidence Recovery Priority", ""])
        for row in recovery_rows[:50]:
            lines.append(
                f"- {row.get('code')} {row.get('stock_name', '')}"
                f" | tier={row.get('evidence_recovery_priority_tier')}"
                f" | master_rank={row.get('master_research_rank') or 'NA'}"
                f" | quant_status={row.get('quant_status') or 'NA'}"
                f" | missing={row.get('missing_evidence_items') or 'none'}"
                f" | next={row.get('next_research_action') or 'recover_v31_evidence'}"
                f" | starter=NOT_ALLOWED"
            )
    (output_dir / "near_buy_research_overlay.md").write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    return rows
''',
)


tests = Path("tests/test_genge_near_buy_research_overlay.py")
test_text = tests.read_text(encoding="utf-8")
if "def _missing_recovery_row" in test_text:
    raise SystemExit("recovery tests already present unexpectedly")
test_addition = r'''


def _missing_recovery_row(**overrides):
    row = _row(
        terminal_reason_codes="hard_gate_unknown:predictability;hard_gate_unknown:long_term_demand;hard_gate_unknown:moat;hard_gate_unknown:financial_safety;hard_gate_unknown:earnings_authenticity",
        source_production_reason_codes="",
        v31_candidate_class="PENDING",
        v31_score_total="",
        v31_hard_gate_unknowns="predictability;long_term_demand;moat;financial_safety;earnings_authenticity",
        v31_score_complete="False",
        v31_normalized_profit_ready="False",
        v31_scenario_valuation_ready="False",
        v31_implied_expectation_ready="False",
        v31_expectation_gap_ready="False",
        v31_risk_adjusted_cagr_ready="False",
        v31_downside_ready="False",
        v31_falsification_ready="False",
        financial_review_status="OK",
        valuation_diagnostic_status="OK",
        quant_status="PRIORITY_RESEARCH",
        long_term_second_pass_status="",
    )
    row.update(overrides)
    return row


def test_missing_hard_gate_evidence_is_recovery_priority_not_near_buy():
    result = classify_terminal_row(_missing_recovery_row())
    assert result["research_opportunity_state"] == "EVIDENCE_RECOVERY_PRIORITY"
    assert result["evidence_recovery_priority_tier"] == "B"
    assert result["near_buy_evidence_state"] == "MISSING"
    assert result["starter_position_advisory_allowed"] is False
    assert result["evidence_recovery_starter_allowed"] is False
    assert result["automatic_promotion_allowed"] is False


def test_completed_non_exit_second_pass_gets_recovery_tier_a_only():
    result = classify_terminal_row(
        _missing_recovery_row(
            long_term_second_pass_status="PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            quant_status="SECONDARY_RESEARCH",
        )
    )
    assert result["research_opportunity_state"] == "EVIDENCE_RECOVERY_PRIORITY"
    assert result["evidence_recovery_priority_tier"] == "A"
    assert result["starter_position_advisory_allowed"] is False


def test_secondary_research_gets_recovery_tier_c():
    result = classify_terminal_row(_missing_recovery_row(quant_status="SECONDARY_RESEARCH"))
    assert result["evidence_recovery_priority_tier"] == "C"


def test_recovery_rejects_negative_conflicted_or_non_execution_rows():
    negative = classify_terminal_row(_missing_recovery_row(source_production_reason_codes="FUNDAMENTAL_BREAK"))
    conflicted = classify_terminal_row(_missing_recovery_row(financial_provider_errors="source_mismatch"))
    blocked = classify_terminal_row(_missing_recovery_row(v31_execution_universe_status="RESEARCH_ONLY"))
    assert negative["research_opportunity_state"] == "NONE"
    assert conflicted["research_opportunity_state"] == "NONE"
    assert blocked["research_opportunity_state"] == "NONE"


def test_overlay_orders_near_buy_then_recovery_a_b_c_then_none():
    near = _row(code="001316", v31_score_total="82")
    rec_a = _missing_recovery_row(code="600001", master_research_rank="2", long_term_second_pass_status="PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES")
    rec_b = _missing_recovery_row(code="600002", master_research_rank="3", quant_status="PRIORITY_RESEARCH")
    rec_c = _missing_recovery_row(code="600003", master_research_rank="4", quant_status="SECONDARY_RESEARCH")
    no = _missing_recovery_row(code="600004", master_research_rank="1", financial_review_status="NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW")
    rows = build_overlay([no, rec_c, rec_b, rec_a, near])
    assert [row["research_opportunity_state"] for row in rows] == [
        "NEAR_BUY",
        "EVIDENCE_RECOVERY_PRIORITY",
        "EVIDENCE_RECOVERY_PRIORITY",
        "EVIDENCE_RECOVERY_PRIORITY",
        "NONE",
    ]
    assert [row["evidence_recovery_priority_tier"] for row in rows[1:4]] == ["A", "B", "C"]


def test_recovery_summary_explicitly_keeps_unknown_non_pass_and_no_starter(tmp_path):
    terminal = tmp_path / "terminal.csv"
    out = tmp_path / "out"
    source = _missing_recovery_row()
    with terminal.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)
    write_overlay(terminal, out)
    summary = json.loads((out / "near_buy_research_summary.json").read_text(encoding="utf-8"))
    assert summary["evidence_recovery_count"] == 1
    assert summary["evidence_recovery_tier_counts"] == {"A": 0, "B": 1, "C": 0}
    assert summary["evidence_recovery_starter_allowed"] is False
    assert summary["unknown_evidence_is_pass"] is False
    assert summary["evidence_recovery_is_formal_signal"] is False
    assert "starter=NOT_ALLOWED" in (out / "near_buy_research_overlay.md").read_text(encoding="utf-8")
'''
tests.write_text(test_text.rstrip() + test_addition + "\n", encoding="utf-8")


workflow = Path(".github/workflows/genge-near-buy-research.yml")
replace_once(
    workflow,
    "on:\n  pull_request:\n",
    'on:\n  push:\n    branches: [main]\n    paths:\n      - "scripts/near_buy_research_overlay.py"\n      - "tests/test_genge_near_buy_research_overlay.py"\n      - ".github/workflows/genge-near-buy-research.yml"\n  pull_request:\n',
)
replace_once(
    workflow,
    "    if: >-\n      (github.event_name == 'workflow_dispatch') ||\n      (\n",
    "    if: >-\n      (github.event_name == 'push') ||\n      (github.event_name == 'workflow_dispatch') ||\n      (\n",
)
replace_once(
    workflow,
    '''          if [ "${{ github.event_name }}" = "workflow_run" ]; then
            upstream="${{ github.event.workflow_run.id }}"
          else
            upstream="${{ inputs.upstream_run_id }}"
          fi
          [[ "$upstream" =~ ^[0-9]+$ ]] || { echo "invalid upstream run id" >&2; exit 1; }
          echo "UPSTREAM_RUN_ID=$upstream" >> "$GITHUB_ENV"
''',
    '''          preferred=""
          if [ "${{ github.event_name }}" = "workflow_run" ]; then
            preferred="${{ github.event.workflow_run.id }}"
          elif [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            preferred="${{ inputs.upstream_run_id }}"
          fi

          candidates=()
          if [[ "$preferred" =~ ^[0-9]+$ ]]; then
            candidates+=("$preferred")
          fi
          mapfile -t successful_runs < <(
            gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/genge-candidate-terminal-review.yml/runs?branch=main&status=success&per_page=20" \
              --jq '.workflow_runs[].id'
          )
          for candidate in "${successful_runs[@]}"; do
            if [[ "$candidate" =~ ^[0-9]+$ ]] && [[ " ${candidates[*]} " != *" $candidate "* ]]; then
              candidates+=("$candidate")
            fi
          done

          upstream=""
          for candidate in "${candidates[@]}"; do
            artifact_id="$(
              gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${candidate}/artifacts?per_page=100" \
                --jq '[.artifacts[] | select(.name == "genge-candidate-terminal-decisions" and .expired == false)][0].id // empty'
            )"
            if [[ "$artifact_id" =~ ^[0-9]+$ ]]; then
              upstream="$candidate"
              echo "selected terminal-review run $candidate with artifact $artifact_id"
              break
            fi
          done
          [[ "$upstream" =~ ^[0-9]+$ ]] || { echo "no successful main terminal-review run has a usable artifact" >&2; exit 1; }
          echo "UPSTREAM_RUN_ID=$upstream" >> "$GITHUB_ENV"
''',
)
replace_once(
    workflow,
    "          assert summary['confirmed_negative_can_be_near_buy'] is False\n          assert summary['automatic_promotion_allowed'] is False\n",
    "          assert summary['confirmed_negative_can_be_near_buy'] is False\n          assert summary['evidence_recovery_starter_allowed'] is False\n          assert summary['unknown_evidence_is_pass'] is False\n          assert summary['evidence_recovery_is_formal_signal'] is False\n          assert summary['automatic_promotion_allowed'] is False\n",
)
replace_once(
    workflow,
    "          assert all(not row['confirmed_negative_items'] for row in rows if row['research_opportunity_state'] == 'NEAR_BUY')\n",
    "          assert all(not row['confirmed_negative_items'] for row in rows if row['research_opportunity_state'] == 'NEAR_BUY')\n          assert all(row['starter_position_advisory_allowed'] == 'False' for row in rows if row['research_opportunity_state'] == 'EVIDENCE_RECOVERY_PRIORITY')\n          assert all(row['evidence_recovery_starter_allowed'] == 'False' for row in rows)\n",
)


changelog = Path("docs/CHANGELOG.md")
text = changelog.read_text(encoding="utf-8")
marker = "## [Unreleased]\n\n"
entry = (
    "- [改进] Near-BUY observer overlay 在 V3.1 正式证据缺失时新增只读 Evidence Recovery Priority A/B/C 队列，"
    "按已完成财务/估值研究、非退出型二次门槛和现有研究优先级确定补证顺序；UNKNOWN 仍不视为 PASS、"
    "缺证据对象不得获得 starter 仓位或自动晋级，并在 Near-BUY 代码合入 main 时用最近成功 Terminal artifact 自动重跑验证。\n"
)
if entry not in text:
    if marker not in text:
        raise SystemExit("Unreleased marker missing")
    changelog.write_text(text.replace(marker, marker + entry, 1), encoding="utf-8")
