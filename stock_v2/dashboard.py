from __future__ import annotations

from typing import Any

from .models import Candidate


def _fmt(v: float | None, digits: int = 2) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def _pct(v: Any) -> str:
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "-"


def _zone(c: Candidate) -> str:
    if c.buy_low is None or c.buy_high is None:
        return "-"
    return f"{c.buy_low:.2f}–{c.buy_high:.2f}"


def render_dashboard(*, run_id: str, generated_at: str, source_meta: dict[str, Any], market: dict[str, Any], candidates: list[Candidate], removed: list[str], total_raw: int) -> str:
    counts = {state: sum(c.state == state for c in candidates) for state in ("BUY", "NEAR_BUY", "WATCH")}
    holdings = [c for c in candidates if c.holding]
    new_or_up = [c for c in candidates if c.change == "NEW" or c.change.startswith("UP")]
    down = [c for c in candidates if c.change.startswith("DOWN")]
    global_ctx = market.get("global") or {}
    global_regime = global_ctx.get("risk_regime") or {}
    pre_open = global_ctx.get("pre_open") or {}
    factors = global_ctx.get("factors") or {}
    transmission = global_ctx.get("security_transmission") or {}

    lines = [
        "# GenGe A股 V2 Clean Dashboard", "",
        f"- run_id: `{run_id}`",
        f"- generated_at: `{generated_at}`",
        f"- data_mode: **{source_meta.get('mode')}**",
        f"- source: `{source_meta.get('source') or '-'}`",
        f"- raw_candidates: **{total_raw}**",
        f"- visible_pool: **{len(candidates)}**",
        f"- BUY / NEAR_BUY / WATCH: **{counts['BUY']} / {counts['NEAR_BUY']} / {counts['WATCH']}**",
        f"- A股环境: **{market.get('status', 'UNKNOWN')}** | external_risk: **{market.get('external_risk', 'UNKNOWN')}**",
        f"- 全球风险偏好: **{global_regime.get('status', 'UNAVAILABLE')}** | score: **{global_regime.get('score', '-')}**", "",
    ]
    if source_meta.get("degraded"):
        lines += [
            "> ⚠️ 降级运行：本次没有读取到新鲜的全 A 扫描产物，使用仓库中已提交的候选快照。",
            "> 结果可以用于研究排序，但新的 BUY/NEAR_BUY 必须等待 live scan 刷新价格和买入区间。", "",
        ]

    lines += ["## 隔夜 / 全球市场", ""]
    if not global_ctx.get("available"):
        lines.append("- global_market_pulse: unavailable")
    else:
        coverage = global_ctx.get("coverage") or {}
        lines += [
            f"- pulse_generated_at: `{global_ctx.get('generated_at') or '-'}`",
            f"- coverage: **{coverage.get('status', 'UNKNOWN')}** | OK {coverage.get('ok_count', '-')}/{coverage.get('instrument_count', '-')} | critical {coverage.get('critical_ok_count', '-')}/{coverage.get('critical_count', '-')}",
            f"- pre_open: **{pre_open.get('status', 'UNKNOWN')}** | holiday_gap_risk: **{pre_open.get('holiday_gap_risk', 'UNKNOWN')}**",
            f"- explicit company transmission mappings: **{len(transmission)}**", "",
            "| 因子 | 24h | A股上次收盘后 | 5d | 新鲜度 |",
            "|---|---:|---:|---:|---|",
        ]
        for factor_id in ("SP500", "NASDAQ", "SOX", "VIX", "US10Y", "DXY", "USDCNH", "HANGSENG", "COPPER", "GOLD", "SILVER", "CRUDE_OIL", "BTC", "ETH"):
            row = factors.get(factor_id)
            if not row:
                continue
            lines.append(f"| {factor_id} | {_pct(row.get('change_24h_pct'))} | {_pct(row.get('since_last_a_share_close_pct'))} | {_pct(row.get('change_5d_pct'))} | {row.get('freshness', '-')} |")
    lines += ["", "## 今日候选池", "",
        "| # | 代码 | 股票 | 行业 | 分数 | 状态 | 置信度 | 现价 | 买入区间 | 距买区 | 变化 |",
        "|---:|---|---|---|---:|---|---|---:|---|---:|---|",
    ]
    for c in candidates:
        dist = "-" if c.distance_to_buy_pct is None else f"{c.distance_to_buy_pct:.2f}%"
        lines.append(f"| {c.rank} | {c.code} | {c.name} | {c.industry} | {c.score:.2f} | **{c.state}** | {c.confidence} | {_fmt(c.current_price)} | {_zone(c)} | {dist} | {c.change} |")

    lines += ["", "## 最接近执行的机会", ""]
    actionable = [c for c in candidates if c.state in {"BUY", "NEAR_BUY"}]
    if not actionable:
        lines.append("当前没有满足 V2 价格/质量条件的 BUY 或 NEAR_BUY。系统不会为了凑数量强造 BUY。")
    else:
        for c in actionable[:10]:
            reason = "；".join(c.reasons[:4]) or "量价/估值/价格计划进入优先区间"
            risk = "；".join(c.risks[:3]) or "仍需核对当日公告与实时价格"
            lines += [
                f"### {c.rank}. {c.name} ({c.code}) — {c.state}",
                f"- 分数/置信度: **{c.score:.2f} / {c.confidence}**",
                f"- 现价/买入区间: **{_fmt(c.current_price)} / {_zone(c)}**",
                f"- 核心理由: {reason}",
                f"- 主要风险: {risk}",
                f"- 证据条数: {len(c.evidence)}", "",
            ]

    lines += ["## 我的持仓映射", ""]
    if not holdings:
        lines.append("当前 Top 池没有匹配到已记录持仓；持仓仍会继续参与下一次全 A 排名。")
    else:
        for c in holdings:
            lines.append(f"- {c.code} {c.name}: **{c.state}** | rank {c.rank} | score {c.score:.2f}")

    lines += ["", "## 今日变化", ""]
    lines.append("- NEW/UP: " + (", ".join(f"{c.code} {c.change}" for c in new_or_up[:15]) or "none"))
    lines.append("- DOWN: " + (", ".join(f"{c.code} {c.change}" for c in down[:15]) or "none"))
    lines.append("- REMOVED: " + (", ".join(removed[:30]) or "none"))

    reasons = market.get("reasons") or []
    lines += [
        "", "## A股市场上下文", "",
        f"- regime: {market.get('status', 'UNKNOWN')}",
        f"- score: {market.get('score') if market.get('score') is not None else '-'}",
        f"- external_risk: {market.get('external_risk', 'UNKNOWN')}",
        f"- reasons: {'；'.join(map(str, reasons)) if reasons else 'none'}",
        f"- source: {market.get('source') or '-'}", "",
        "## V2 决策规则", "",
        "- 全 A 扫描负责事实、量化、价格计划；V2 单独负责最终排名和 BUY/NEAR_BUY/WATCH。",
        "- 全球市场只通过明确到证券代码且有证据的 transmission 微调排序，不凭行业印象猜映射，也不单独制造 BUY。",
        "- `HARD_REJECT` 才是硬否决；证据缺口降低置信度，但不会把候选从池子里抹掉。",
        "- BUY 不设最低数量；候选池有数据时尽量保持 20–30 只，并执行行业分散。",
        "- 没有可靠买入区间时绝不编造价格，状态保持 WATCH。",
        "- 这是研究与决策辅助，不连接券商、不自动下单。", "",
    ]
    return "\n".join(lines) + "\n"
