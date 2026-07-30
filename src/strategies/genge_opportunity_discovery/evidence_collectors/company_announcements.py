"""Company announcement collectors for official exchange/public filings."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests

from .cache import EvidenceCache
from .validators import content_hash, direction_from_excerpt, extract_numeric_context, extract_text_from_response, source_domain, utc_now


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}
CNINFO_STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
MATERIAL_EVENT_WINDOW_DAYS = 730
# CNINFO currently caps this endpoint at 30 rows even when a larger pageSize is
# requested.  Match the provider contract so a full 30-row page advances to the
# next page instead of being mistaken for the last page.  The total request cap
# remains 600 metadata rows per company.
MATERIAL_EVENT_PAGE_SIZE = 30
MATERIAL_EVENT_MAX_PAGES = 20
MATERIAL_EVENT_MAX_DOCUMENTS = 16

MATERIAL_EVENT_RULES: tuple[tuple[str, re.Pattern[str], int, str], ...] = (
    ("DELISTING_RISK", re.compile(r"终止上市|退市风险警示|可能被终止上市|股票退市|恢复上市"), 730, "HIGH"),
    ("OTHER_RISK_WARNING", re.compile(r"实施其他风险警示|被实施其他风险警示|撤销其他风险警示"), 730, "HIGH"),
    (
        "BANKRUPTCY_RESTRUCTURING",
        re.compile(r"破产清算|申请破产|被申请破产|破产重整|预重整|重整申请|法院受理.{0,12}重整"),
        730,
        "HIGH",
    ),
    (
        "REGULATORY_INVESTIGATION",
        re.compile(r"立案调查|立案告知书|立案通知书|立案决定书|(?:收到|被)(?:中国证监会|证监会|监管机构|证券监管部门|公安机关).{0,30}立案"),
        730,
        "HIGH",
    ),
    ("REGULATORY_PENALTY", re.compile(r"行政处罚|纪律处分"), 730, "HIGH"),
    ("ACCOUNTING_FRAUD", re.compile(r"财务造假|虚假记载|欺诈发行|虚假陈述"), 730, "HIGH"),
    (
        "REGULATORY_ACTION",
        re.compile(r"监管措施|责令改正|自律监管|(?<!不)(?<!未)(?:涉嫌|存在|发生).{0,10}违规|违规(?:行为|事项)"),
        120,
        "MEDIUM",
    ),
    ("NON_STANDARD_AUDIT", re.compile(r"非标准审计意见|非标意见|保留意见|无法表示意见|否定意见"), 730, "HIGH"),
    ("DEBT_DEFAULT", re.compile(r"债务违约|债务逾期|贷款逾期|票据逾期|未能清偿"), 730, "HIGH"),
    (
        "FUNDS_OCCUPATION",
        re.compile(
            r"(?:控股股东|实际控制人|关联方|关联人).{0,24}(?:占用|非经营性占用)"
            r"|(?:存在|发生|形成|新增|发现|涉及).{0,12}(?:非经营性)?资金占用"
            r"|(?:非经营性)?资金占用(?:事项|问题|行为|风险)"
            r"|占用(?:上市)?公司资金"
            r"|(?:资金占用|占用资金).{0,12}(?:归还|清偿|整改|解决)"
            r"|不存在.{0,12}资金占用"
        ),
        730,
        "HIGH",
    ),
    ("ILLEGAL_GUARANTEE", re.compile(r"违规担保|担保逾期|担保代偿"), 730, "HIGH"),
    ("PLEDGE_DEFAULT", re.compile(r"质押违约|强制平仓|平仓风险|被动减持"), 730, "HIGH"),
    ("MAJOR_LITIGATION_ARBITRATION", re.compile(r"重大诉讼|重大仲裁|累计诉讼、?仲裁|涉及诉讼、?仲裁"), 365, "HIGH"),
    ("SHARE_FREEZE", re.compile(r"(?:股份|股权|股票).{0,12}(?:冻结|轮候冻结)|(?:冻结|轮候冻结).{0,12}(?:股份|股权|股票)"), 180, "MEDIUM"),
    ("SAFETY_ACCIDENT", re.compile(r"安全事故|重大事故|生产事故"), 120, "HIGH"),
    ("PRODUCTION_HALT", re.compile(r"停产|停工|恢复生产|恢复经营|复工复产"), 120, "MEDIUM"),
    ("LOSS_WARNING", re.compile(r"预亏|预计亏损|业绩预告.{0,12}亏损"), 120, "MEDIUM"),
    ("SHARE_REDUCTION", re.compile(r"减持计划|拟减持|计划减持|大额减持"), 180, "MEDIUM"),
    ("CONTROL_CHANGE", re.compile(r"控制权变更|实际控制人变更|控股股东变更"), 180, "MEDIUM"),
    ("MAJOR_ASSET_IMPAIRMENT", re.compile(r"重大资产减值|计提.{0,10}大额.{0,6}减值|大额减值准备"), 180, "MEDIUM"),
)

RESOLVED_EVENT_PATTERNS: Mapping[str, tuple[re.Pattern[str], ...]] = {
    "DELISTING_RISK": (
        re.compile(r"(?:撤销|解除).{0,12}退市风险警示|退市风险警示.{0,12}(?:撤销|解除)|恢复上市"),
    ),
    "OTHER_RISK_WARNING": (
        re.compile(r"(?:撤销|解除).{0,12}其他风险警示|其他风险警示.{0,12}(?:撤销|解除)"),
    ),
    "BANKRUPTCY_RESTRUCTURING": (
        re.compile(r"重整计划执行完毕|终结破产程序|撤回.{0,12}破产申请|不予受理.{0,12}破产"),
    ),
    "REGULATORY_INVESTIGATION": (
        re.compile(r"立案(?:调查)?.{0,12}(?:终结|终止|撤销)|(?:调查终结|终止调查)"),
        re.compile(r"撤销(?:本次|该次|上述)?立案|未收到.{0,12}立案"),
    ),
    "REGULATORY_PENALTY": (
        re.compile(r"撤销(?:本次|该次|上述)?(?:行政)?处罚|不予处罚|不存在.{0,12}处罚"),
    ),
    "REGULATORY_ACTION": (
        re.compile(r"撤销.{0,12}监管措施|整改完成|完成整改|不存在.{0,12}违规|未发现.{0,12}违规"),
    ),
    "NON_STANDARD_AUDIT": (
        re.compile(r"非标.{0,18}(?:影响已消除|事项已消除)"),
    ),
    "DEBT_DEFAULT": (
        re.compile(r"(?:债务|贷款|票据|逾期).{0,12}(?:已偿还|已清偿|已解决)"),
        re.compile(r"不存在.{0,12}逾期"),
    ),
    "FUNDS_OCCUPATION": (
        re.compile(r"占用资金.{0,12}(?:已全部归还|已全部清偿)|不存在.{0,12}资金占用"),
    ),
    "ILLEGAL_GUARANTEE": (
        re.compile(r"违规担保.{0,12}(?:已全部解除|责任已解除)|不存在.{0,12}违规担保"),
    ),
    "PLEDGE_DEFAULT": (
        re.compile(r"(?:质押违约|平仓)风险.{0,12}(?:已解除|已消除)"),
    ),
    "SHARE_FREEZE": (
        re.compile(r"解除.{0,12}冻结|冻结.{0,12}解除|股份解冻|未被冻结|不存在.{0,12}冻结"),
    ),
    "PRODUCTION_HALT": (
        re.compile(r"恢复(?:生产|经营)|复工复产|解除.{0,12}(?:停产|停工)|不(?:会)?停产|无需停产"),
    ),
    "LOSS_WARNING": (
        re.compile(r"修正后.{0,12}(?:盈利|扭亏)|扭亏为盈"),
    ),
    "SHARE_REDUCTION": (
        re.compile(r"(?:终止|提前终止).{0,12}减持|减持.{0,12}(?:终止|完成|实施完毕|时间届满)|不减持|不存在.{0,12}减持计划"),
    ),
    "CONTROL_CHANGE": (
        re.compile(r"(?:终止|提前终止).{0,12}控制权变更|控制权变更.{0,12}(?:终止|完成)"),
    ),
}

FULL_RESOLUTION_PATTERNS: Mapping[str, tuple[re.Pattern[str], ...]] = {
    "SHARE_FREEZE": (
        re.compile(r"全部.{0,12}(?:解除冻结|解冻)|(?:冻结|冻结股份).{0,12}已全部解除|不存在.{0,12}冻结|未被冻结"),
    ),
    "DEBT_DEFAULT": (
        re.compile(r"(?:债务|贷款|票据|逾期).{0,12}(?:已全部偿还|已全部清偿)|不存在.{0,12}逾期"),
    ),
    "FUNDS_OCCUPATION": RESOLVED_EVENT_PATTERNS["FUNDS_OCCUPATION"],
    "ILLEGAL_GUARANTEE": RESOLVED_EVENT_PATTERNS["ILLEGAL_GUARANTEE"],
}

FUNDS_OCCUPATION_ROUTINE_REPORT_RE = re.compile(
    r"专项(?:说明|审计报告|审核报告|核查意见|报告)|鉴证报告"
)
FUNDS_OCCUPATION_INCIDENT_ASSERTION_RE = re.compile(
    r"存在|发生|形成|新增|发现|涉及|违规|事项|问题|风险|整改|归还|清偿|解决"
)


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _clean_title(value: Any) -> str:
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _cninfo_publish_date(value: Any) -> date | None:
    try:
        timestamp = int(value or 0) / 1000
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, tz=SHANGHAI_TIMEZONE).date()


def _resolution_scope(event_type: str, text: str, *, resolved: bool) -> str:
    if not resolved:
        return "NONE"
    explicit_full = FULL_RESOLUTION_PATTERNS.get(event_type)
    if explicit_full is not None:
        return "FULL" if any(pattern.search(text) for pattern in explicit_full) else "PARTIAL"
    if "部分" in text and event_type in {
        "SHARE_FREEZE", "DEBT_DEFAULT", "FUNDS_OCCUPATION", "ILLEGAL_GUARANTEE",
        "MAJOR_LITIGATION_ARBITRATION",
    }:
        return "PARTIAL"
    return "FULL"


def _classify_material_events(title: Any, *, publish_date: date, as_of: date) -> list[dict[str, Any]]:
    """Return every independently classified risk in one announcement title."""

    text = _clean_title(title)
    result: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for event_type, pattern, ttl_days, severity in MATERIAL_EVENT_RULES:
        match = pattern.search(text)
        if not match or event_type in seen_types:
            continue
        if (
            event_type == "FUNDS_OCCUPATION"
            and FUNDS_OCCUPATION_ROUTINE_REPORT_RE.search(text)
            and not FUNDS_OCCUPATION_INCIDENT_ASSERTION_RE.search(text)
        ):
            # Annual auditor/accountant verification titles describe the scope
            # of a routine review, not a finding that occupation occurred.
            continue
        seen_types.add(event_type)
        resolved = any(
            candidate.search(text) for candidate in RESOLVED_EVENT_PATTERNS.get(event_type, ())
        )
        # “终止上市”本身是退市风险，而不是风险已经解除。
        if event_type == "DELISTING_RISK" and "终止上市" in text:
            resolved = False
        resolution_scope = _resolution_scope(event_type, text, resolved=resolved)
        valid_until = publish_date + timedelta(days=ttl_days)
        # A partial unfreeze/repayment does not close the underlying risk.  It is
        # retained as ACTIVE until a clearly full resolution is observed.
        status = (
            "RESOLVED" if resolved and resolution_scope == "FULL"
            else "EXPIRED" if valid_until < as_of
            else "ACTIVE"
        )
        result.append({
            "event_type": event_type,
            "event_severity": severity,
            "event_status": status,
            "event_resolution_scope": resolution_scope,
            "risk_valid_until": valid_until.isoformat(),
            "direction": "NEGATIVE" if status == "ACTIVE" else "NEUTRAL",
            "matched_term": match.group(0),
        })
    return result


def _classify_material_event(title: Any, *, publish_date: date, as_of: date) -> dict[str, Any] | None:
    """Backward-compatible single-event helper; collection uses the plural form."""

    events = _classify_material_events(title, publish_date=publish_date, as_of=as_of)
    return events[0] if events else None


def _material_event_excerpt(text: str, *, matched_term: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in lines:
        if matched_term and matched_term in line:
            return line[:800]
    return (lines[0][:800] if lines else "")


def _load_cninfo_org_ids(session: requests.Session, timeout: int) -> dict[str, str]:
    response = session.get(
        CNINFO_STOCK_LIST_URL,
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        timeout=timeout,
    )
    response.raise_for_status()
    stock_list = response.json().get("stockList") or []
    return {
        _normalize_code(item.get("code")): str(item.get("orgId") or "").strip()
        for item in stock_list
        if _normalize_code(item.get("code")) and str(item.get("orgId") or "").strip()
    }


def _query_cninfo(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> list[dict[str, Any]]:
    start = (as_of - timedelta(days=560)).isoformat()
    end = as_of.isoformat()
    is_shanghai = code.startswith(("6", "9"))
    data = {
        "pageNum": "1",
        "pageSize": "5",
        "column": "sse" if is_shanghai else "szse",
        "tabName": "fulltext",
        "plate": "sh" if is_shanghai else "sz",
        "stock": f"{code},{org_id}",
        "searchkey": "年度报告",
        "secid": "",
        "category": "category_ndbg_szsh",
        "trade": "",
        "seDate": f"{start}~{end}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    response = session.post(
        "https://www.cninfo.com.cn/new/hisAnnouncement/query",
        headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
        data=data,
        timeout=timeout,
    )
    response.raise_for_status()
    announcements = (response.json().get("announcements") or [])
    result: list[dict[str, Any]] = []
    for item in announcements:
        title = _clean_title(item.get("announcementTitle"))
        if "英文" in title:
            continue
        adjunct = str(item.get("adjunctUrl") or "")
        if not adjunct:
            continue
        parsed_date = _cninfo_publish_date(item.get("announcementTime"))
        if parsed_date is None or parsed_date > as_of:
            continue
        result.append(
            {
                "title": title,
                "publish_date": parsed_date.isoformat(),
                "url": f"https://static.cninfo.com.cn/{adjunct}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "cninfo",
            }
        )
    return sorted(
        result,
        key=lambda item: (str(item.get("publish_date") or ""), "摘要" not in str(item.get("title") or "")),
        reverse=True,
    )


def _query_sse(code: str, as_of: date, session: requests.Session, timeout: int) -> list[dict[str, Any]]:
    params = {
        "jsonCallBack": "",
        "isPagination": "true",
        "productId": code,
        "keyWord": "年度报告",
        "securityType": "0101,120100,020100,020200,120200",
        "reportType2": "DQBG",
        "pageHelp.pageSize": "5",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "pageHelp.endPage": "1",
    }
    response = session.get(
        "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
        params=params,
        headers={**REQUEST_HEADERS, "Referer": "https://www.sse.com.cn/"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json().get("pageHelp", {}).get("data") or []
    result: list[dict[str, Any]] = []
    for item in data:
        publish_date = str(item.get("SSEDATE") or "")[:10]
        if publish_date and publish_date > as_of.isoformat():
            continue
        url = str(item.get("URL") or "")
        if not url:
            continue
        result.append(
            {
                "title": _clean_title(item.get("TITLE")),
                "publish_date": publish_date,
                "url": f"https://www.sse.com.cn{url}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "sse",
            }
        )
    return result


def _query_cninfo_material_events(
    code: str,
    org_id: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = as_of - timedelta(days=MATERIAL_EVENT_WINDOW_DAYS)
    is_shanghai = code.startswith(("6", "9"))
    result: list[dict[str, Any]] = []
    reported_total = 0
    pages_fetched = 0
    last_page_count = 0
    query_error = ""
    for page in range(1, MATERIAL_EVENT_MAX_PAGES + 1):
        data = {
            "pageNum": str(page),
            "pageSize": str(MATERIAL_EVENT_PAGE_SIZE),
            "column": "sse" if is_shanghai else "szse",
            "tabName": "fulltext",
            "plate": "sh" if is_shanghai else "sz",
            "stock": f"{code},{org_id}",
            "searchkey": "",
            "secid": "",
            "category": "",
            "trade": "",
            "seDate": f"{start.isoformat()}~{as_of.isoformat()}",
            "sortName": "time",
            "sortType": "desc",
            "isHLtitle": "true",
        }
        try:
            response = session.post(
                "https://www.cninfo.com.cn/new/hisAnnouncement/query",
                headers={**REQUEST_HEADERS, "Referer": "https://www.cninfo.com.cn/"},
                data=data,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("cninfo_material_event_response_not_object")
            if "announcements" not in payload or "totalAnnouncement" not in payload:
                raise ValueError("cninfo_material_event_response_schema_missing")
            try:
                page_total = int(payload.get("totalAnnouncement") or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError("cninfo_material_event_total_invalid") from exc
            if page_total < 0:
                raise ValueError("cninfo_material_event_total_invalid")
            raw_announcements = payload.get("announcements")
            if raw_announcements is None and page_total == 0:
                raw_announcements = []
            if not isinstance(raw_announcements, list):
                raise ValueError("cninfo_material_event_announcements_invalid")
            if raw_announcements and page_total == 0:
                raise ValueError("cninfo_material_event_total_inconsistent")
        except Exception as exc:
            if not pages_fetched:
                raise
            query_error = f"{type(exc).__name__}: {exc}"
            break
        announcements = raw_announcements
        last_page_count = len(announcements)
        pages_fetched += 1
        try:
            reported_total = max(reported_total, page_total)
        except (TypeError, ValueError):
            pass
        for item in announcements:
            title = _clean_title(item.get("announcementTitle"))
            parsed_date = _cninfo_publish_date(item.get("announcementTime"))
            adjunct = str(item.get("adjunctUrl") or "").strip()
            if (
                not title
                or "英文" in title
                or parsed_date is None
                or parsed_date < start
                or parsed_date > as_of
                or not adjunct
            ):
                continue
            result.append({
                "title": title,
                "publish_date": parsed_date.isoformat(),
                "url": f"https://static.cninfo.com.cn/{adjunct.lstrip('/')}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "cninfo",
            })
        if len(announcements) < MATERIAL_EVENT_PAGE_SIZE:
            break
        if reported_total and page * MATERIAL_EVENT_PAGE_SIZE >= reported_total:
            break
    deduped = list({str(item["url"]): item for item in result}.values())
    return deduped, {
        "pages_fetched": pages_fetched,
        "reported_total": reported_total,
        "query_error": query_error,
        "truncated": bool(
            query_error
            or (reported_total and reported_total > pages_fetched * MATERIAL_EVENT_PAGE_SIZE)
            or (
                pages_fetched == MATERIAL_EVENT_MAX_PAGES
                and last_page_count >= MATERIAL_EVENT_PAGE_SIZE
            )
        ),
    }


def _query_sse_material_events(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    start = as_of - timedelta(days=MATERIAL_EVENT_WINDOW_DAYS)
    result: list[dict[str, Any]] = []
    pages_fetched = 0
    reported_pages = 1
    query_error = ""
    for page in range(1, MATERIAL_EVENT_MAX_PAGES + 1):
        params = {
            "jsonCallBack": "",
            "isPagination": "true",
            "productId": code,
            "keyWord": "",
            "securityType": "0101,120100,020100,020200,120200",
            "reportType2": "",
            "pageHelp.pageSize": str(MATERIAL_EVENT_PAGE_SIZE),
            "pageHelp.pageNo": str(page),
            "pageHelp.beginPage": str(page),
            "pageHelp.cacheSize": "1",
            "pageHelp.endPage": str(page),
            "beginDate": start.isoformat(),
            "endDate": as_of.isoformat(),
        }
        try:
            response = session.get(
                "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do",
                params=params,
                headers={**REQUEST_HEADERS, "Referer": "https://www.sse.com.cn/"},
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping) or not isinstance(payload.get("pageHelp"), Mapping):
                raise ValueError("sse_material_event_response_schema_missing")
            page_help = payload["pageHelp"]
            if "data" not in page_help or "pageCount" not in page_help:
                raise ValueError("sse_material_event_page_schema_missing")
            raw_announcements = page_help.get("data")
            if raw_announcements is None:
                raw_announcements = []
            if not isinstance(raw_announcements, list):
                raise ValueError("sse_material_event_data_invalid")
            try:
                current_page_count = int(page_help.get("pageCount") or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError("sse_material_event_page_count_invalid") from exc
            if current_page_count < 0:
                raise ValueError("sse_material_event_page_count_invalid")
            if raw_announcements and current_page_count == 0:
                raise ValueError("sse_material_event_page_count_inconsistent")
        except Exception as exc:
            if not pages_fetched:
                raise
            query_error = f"{type(exc).__name__}: {exc}"
            break
        announcements = raw_announcements
        pages_fetched += 1
        try:
            reported_pages = max(reported_pages, current_page_count or 1)
        except (TypeError, ValueError):
            pass
        for item in announcements:
            title = _clean_title(item.get("TITLE"))
            try:
                parsed_date = date.fromisoformat(str(item.get("SSEDATE") or "")[:10])
            except ValueError:
                continue
            url = str(item.get("URL") or "").strip()
            if not title or parsed_date < start or parsed_date > as_of or not url:
                continue
            result.append({
                "title": title,
                "publish_date": parsed_date.isoformat(),
                "url": url if url.startswith(("http://", "https://")) else f"https://www.sse.com.cn{url}",
                "source_type": "EXCHANGE_DISCLOSURE",
                "source_name": "sse",
            })
        if not announcements or page >= reported_pages:
            break
    deduped = list({str(item["url"]): item for item in result}.values())
    return deduped, {
        "pages_fetched": pages_fetched,
        "reported_total": "",
        "query_error": query_error,
        "truncated": bool(query_error or reported_pages > MATERIAL_EVENT_MAX_PAGES),
    }


def _material_event_candidates(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
    cninfo_org_ids: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    org_id = str(cninfo_org_ids.get(code) or "").strip()
    if org_id:
        return _query_cninfo_material_events(code, org_id, as_of, session, timeout)
    if code.startswith("6"):
        return _query_sse_material_events(code, as_of, session, timeout)
    raise RuntimeError("official_material_event_endpoint_unavailable")


def _effective_material_event_representatives(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep one current lifecycle representative per event type."""

    by_type: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        if event_type:
            by_type.setdefault(event_type, []).append(event)
    representatives: list[dict[str, Any]] = []
    for event_type, typed_events in by_type.items():
        ordered = sorted(
            typed_events,
            key=lambda item: (str(item.get("publish_date") or ""), str(item.get("url") or "")),
        )
        full_resolutions = [
            item for item in ordered
            if str(item.get("event_status") or "").upper() == "RESOLVED"
            and str(item.get("event_resolution_scope") or "").upper() == "FULL"
        ]
        last_full_date = str(full_resolutions[-1].get("publish_date") or "") if full_resolutions else ""
        active_after_resolution = [
            item for item in ordered
            if str(item.get("event_status") or "").upper() == "ACTIVE"
            and str(item.get("publish_date") or "") > last_full_date
        ]
        if active_after_resolution:
            representative = active_after_resolution[-1]
        elif full_resolutions:
            representative = full_resolutions[-1]
        else:
            non_expired = [
                item for item in ordered
                if str(item.get("event_status") or "").upper() != "EXPIRED"
            ]
            if not non_expired:
                continue
            representative = non_expired[-1]
        representatives.append({**representative, "event_type": event_type})
    return sorted(
        representatives,
        key=lambda item: (
            str(item.get("event_status") or "").upper() == "ACTIVE",
            str(item.get("event_severity") or "").upper() == "HIGH",
            str(item.get("publish_date") or ""),
            str(item.get("event_type") or ""),
        ),
        reverse=True,
    )


def _announcement_candidates(
    code: str,
    as_of: date,
    session: requests.Session,
    timeout: int,
    cninfo_org_ids: Mapping[str, str],
) -> list[dict[str, Any]]:
    org_id = str(cninfo_org_ids.get(code) or "").strip()
    if org_id:
        return _query_cninfo(code, org_id, as_of, session, timeout)
    if code.startswith("6"):
        return _query_sse(code, as_of, session, timeout)
    return []


def _audit_row(
    *,
    code: str,
    stock_name: Any,
    industry: Any,
    collector: str,
    status: str,
    issue: str,
    detail: str,
    url: str = "",
    title: str = "",
    cache_hit: bool = False,
) -> dict[str, Any]:
    return {
        "scope": "company",
        "code": code,
        "stock_name": stock_name or "",
        "industry": industry or "",
        "collector": collector,
        "status": status,
        "issue": issue,
        "detail": detail,
        "original_url": url,
        "source_domain": source_domain(url),
        "title": title,
        "collected_at": utc_now(),
        "cache_hit": cache_hit,
    }


def collect_company_announcements(
    *,
    rows: list[Mapping[str, Any]],
    as_of: date,
    cache: EvidenceCache,
    limit: int = 50,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    session = requests.Session()
    evidence_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    network_fetches = 0
    fetch_successes = 0
    task_count = 0
    cninfo_org_ids: dict[str, str] = {}
    if rows[: max(0, int(limit))]:
        try:
            cninfo_org_ids = _load_cninfo_org_ids(session, timeout)
            network_fetches += 1
        except Exception:
            cninfo_org_ids = {}

    for row in rows[: max(0, int(limit))]:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        task_count += 1
        collector = (
            "cninfo_company_announcement"
            if cninfo_org_ids.get(code)
            else "sse_company_announcement"
        )
        report_period = str(as_of.year - 1)
        key = cache.key_for(
            {
                "collector": collector,
                "code": code,
                "announcement_type": "annual_report",
                "report_period": report_period,
                "version": 4,
            }
        )
        cached = cache.get(key)
        if cached is not None:
            evidence_rows.extend(cached.get("evidence_rows") or [])
            for audit in cached.get("audit_rows") or []:
                audit = dict(audit)
                audit["cache_hit"] = True
                audit_rows.append(audit)
            continue

        task_evidence: list[dict[str, Any]] = []
        task_audit: list[dict[str, Any]] = []
        try:
            announcements = _announcement_candidates(code, as_of, session, timeout, cninfo_org_ids)
            network_fetches += 1
        except Exception as exc:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="announcement_query_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        if not announcements:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="MISSING",
                    issue="announcement_not_found",
                    detail="No annual-report announcement found on the official disclosure endpoint.",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        item = announcements[0]
        url = str(item.get("url") or "")
        source_name = str(item.get("source_name") or "")
        referer = "https://www.sse.com.cn/" if source_name == "sse" else "https://www.cninfo.com.cn/"
        try:
            response = session.get(url, headers={**REQUEST_HEADERS, "Referer": referer}, timeout=timeout)
            network_fetches += 1
            response.raise_for_status()
            text, parser = extract_text_from_response(response.content, response.headers.get("content-type", ""))
        except Exception as exc:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="announcement_fetch_or_parse_failed",
                    detail=f"{type(exc).__name__}: {exc}",
                    url=url,
                    title=item.get("title") or "",
                )
            )
            audit_rows.extend(task_audit)
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})
            continue

        if text:
            fetch_successes += 1
        extracted = extract_numeric_context(
            text,
            keywords=["营业收入", "净利润", "现金流", "revenue", "profit", "cash flow", "operating revenue"],
        )
        raw_hash = content_hash(response.content)
        if not extracted:
            task_audit.append(
                _audit_row(
                    code=code,
                    stock_name=row.get("stock_name"),
                    industry=row.get("normalized_industry"),
                    collector=collector,
                    status="FAILED",
                    issue="numeric_value_not_located_in_original",
                    detail=f"Original fetched and parsed by {parser}, but no numeric context matched required keywords.",
                    url=url,
                    title=item.get("title") or "",
                )
            )
        else:
            excerpt = extracted["excerpt"]
            task_evidence.append(
                {
                    "date": item.get("publish_date") or as_of.isoformat(),
                    "publish_date": item.get("publish_date") or as_of.isoformat(),
                    "scope": "company",
                    "code": code,
                    "stock_name": row.get("stock_name") or "",
                    "industry": row.get("normalized_industry") or "",
                    "evidence_name": "定期报告原文数值",
                    "indicator": "定期报告原文数值",
                    "evidence_value": excerpt,
                    "value": extracted["value"],
                    "unit": extracted["unit"],
                    "comparison_period": item.get("publish_date") or "",
                    "evidence_direction": direction_from_excerpt(excerpt),
                    "direction": direction_from_excerpt(excerpt),
                    "source": url,
                    "original_url": url,
                    "source_domain": source_domain(url),
                    "source_type": item.get("source_type") or "EXCHANGE_DISCLOSURE",
                    "confidence": "HIGH",
                    "raw_excerpt": excerpt,
                    "normalized_summary": f"{item.get('title')}：{excerpt}",
                    "title": item.get("title") or "",
                    "parser": collector,
                    "collector": collector,
                    "parse_status": "OK",
                    "evidence_status": "VERIFIED",
                    "content_hash": raw_hash,
                    "extraction_confidence": "HIGH",
                    "warning_flags": "",
                }
            )
        audit_rows.extend(task_audit)
        evidence_rows.extend(task_evidence)
        cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})

    summary = {
        "company_task_count": task_count,
        "company_actual_fetch_count": network_fetches,
        "company_fetch_success_count": fetch_successes,
        "company_evidence_rows": len(evidence_rows),
        "company_failure_count": sum(1 for row in audit_rows if row.get("status") == "FAILED"),
        "company_missing_count": sum(1 for row in audit_rows if row.get("status") == "MISSING"),
    }
    return evidence_rows, audit_rows, summary


def collect_company_material_events(
    *,
    rows: list[Mapping[str, Any]],
    as_of: date,
    cache: EvidenceCache,
    limit: int = 50,
    timeout: int = 12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Collect recent official material-event filings without keyword-query fanout."""

    session = requests.Session()
    evidence_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    network_fetches = 0
    document_fetch_successes = 0
    task_count = 0
    targets = rows[: max(0, int(limit))]
    cninfo_org_ids: dict[str, str] = {}
    if targets:
        try:
            cninfo_org_ids = _load_cninfo_org_ids(session, timeout)
            network_fetches += 1
        except Exception:
            cninfo_org_ids = {}

    for row in targets:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        task_count += 1
        provider_collector = "cninfo_material_event" if cninfo_org_ids.get(code) else "sse_material_event"
        audit_collector = "official_material_event_scan"
        key = cache.key_for({
            "collector": audit_collector,
            "provider": provider_collector,
            "code": code,
            "announcement_type": "material_events",
            "as_of_date": as_of.isoformat(),
            "window_days": MATERIAL_EVENT_WINDOW_DAYS,
            "version": 2,
        })
        cached = cache.get(key)
        if cached is not None:
            evidence_rows.extend(cached.get("evidence_rows") or [])
            for audit in cached.get("audit_rows") or []:
                local_audit = dict(audit)
                local_audit["cache_hit"] = True
                audit_rows.append(local_audit)
            continue

        task_evidence: list[dict[str, Any]] = []
        try:
            announcements, query_meta = _material_event_candidates(
                code, as_of, session, timeout, cninfo_org_ids,
            )
            network_fetches += int(query_meta.get("pages_fetched") or 0)
        except Exception as exc:
            network_fetches += 1
            task_audit = [_audit_row(
                code=code,
                stock_name=row.get("stock_name"),
                industry=row.get("normalized_industry"),
                collector=audit_collector,
                status="FAILED",
                issue="material_event_scan_failed",
                detail=f"{type(exc).__name__}: {exc}",
            )]
            audit_rows.extend(task_audit)
            continue

        matched: list[dict[str, Any]] = []
        for announcement in announcements:
            try:
                publish_date = date.fromisoformat(str(announcement.get("publish_date") or ""))
            except ValueError:
                continue
            classifications = _classify_material_events(
                announcement.get("title"), publish_date=publish_date, as_of=as_of,
            )
            matched.extend({**announcement, **classification} for classification in classifications)
        representatives = _effective_material_event_representatives(matched)

        active_representatives = [
            item for item in representatives
            if str(item.get("event_status") or "").upper() == "ACTIVE"
        ]
        selected = representatives[:MATERIAL_EVENT_MAX_DOCUMENTS]
        selected_active_types = {
            str(item.get("event_type") or "") for item in selected
            if str(item.get("event_status") or "").upper() == "ACTIVE"
        }
        uncovered_active_types = sorted({
            str(item.get("event_type") or "") for item in active_representatives
        } - selected_active_types)
        active_failures: list[str] = []
        nonblocking_failures: list[str] = []
        document_cache: dict[str, tuple[bytes, str, str]] = {}
        for item in selected:
            url = str(item.get("url") or "")
            source_name = str(item.get("source_name") or "")
            referer = "https://www.sse.com.cn/" if source_name == "sse" else "https://www.cninfo.com.cn/"
            try:
                cached_document = document_cache.get(url)
                if cached_document is None:
                    response = session.get(
                        url,
                        headers={**REQUEST_HEADERS, "Referer": referer},
                        timeout=timeout,
                    )
                    network_fetches += 1
                    response.raise_for_status()
                    text, parser = extract_text_from_response(
                        response.content, response.headers.get("content-type", ""),
                    )
                    cached_document = (response.content, text, parser)
                    document_cache[url] = cached_document
                    document_fetch_successes += 1
                raw_content, text, parser = cached_document
                excerpt = _material_event_excerpt(
                    text, matched_term=str(item.get("matched_term") or ""),
                )
                if not excerpt:
                    raise ValueError(f"material_event_original_parse_empty:{parser}")
            except Exception as exc:
                failure = f"{item.get('event_type')}:{type(exc).__name__}:{exc}"
                if str(item.get("event_status") or "").upper() == "ACTIVE":
                    active_failures.append(failure)
                else:
                    nonblocking_failures.append(failure)
                continue
            event_status = str(item.get("event_status") or "EXPIRED")
            direction = "NEGATIVE" if event_status == "ACTIVE" else "NEUTRAL"
            title = str(item.get("title") or "")
            task_evidence.append({
                "date": item.get("publish_date") or as_of.isoformat(),
                "publish_date": item.get("publish_date") or as_of.isoformat(),
                "scope": "company",
                "code": code,
                "stock_name": row.get("stock_name") or "",
                "industry": row.get("normalized_industry") or row.get("industry") or "",
                "evidence_kind": "material_event",
                "event_type": item.get("event_type") or "",
                "event_severity": item.get("event_severity") or "MEDIUM",
                "event_status": event_status,
                "event_resolution_scope": item.get("event_resolution_scope") or "NONE",
                "risk_valid_until": item.get("risk_valid_until") or "",
                "evidence_name": f"重大事件:{item.get('event_type')}",
                "indicator": f"重大事件:{item.get('event_type')}",
                "evidence_value": title,
                "value": title,
                "unit": "",
                "comparison_period": item.get("publish_date") or "",
                "evidence_direction": direction,
                "direction": direction,
                "source": url,
                "original_url": url,
                "source_domain": source_domain(url),
                "source_type": item.get("source_type") or "EXCHANGE_DISCLOSURE",
                "confidence": "HIGH",
                "raw_excerpt": excerpt,
                "normalized_summary": f"{title}：{excerpt}",
                "title": title,
                "parser": parser,
                "collector": provider_collector,
                "parse_status": "OK",
                "evidence_status": "VERIFIED",
                "content_hash": content_hash(raw_content),
                "extraction_confidence": "HIGH",
                "warning_flags": "" if event_status == "ACTIVE" else f"material_event_{event_status.lower()}",
            })

        partial_reasons: list[str] = []
        if query_meta.get("truncated"):
            partial_reasons.append("announcement_pages_truncated")
        if query_meta.get("query_error"):
            partial_reasons.append(f"announcement_query_partial:{query_meta.get('query_error')}")
        if uncovered_active_types:
            partial_reasons.append(f"uncovered_active_event_types:{','.join(uncovered_active_types)}")
        if active_failures:
            partial_reasons.append(";".join(active_failures))
        audit_status = "PARTIAL" if partial_reasons else "OK"
        task_audit = [_audit_row(
            code=code,
            stock_name=row.get("stock_name"),
            industry=row.get("normalized_industry") or row.get("industry"),
            collector=audit_collector,
            status=audit_status,
            issue="material_event_scan_complete",
            detail=(
                f"announcements={len(announcements)};matched={len(matched)};"
                f"representatives={len(representatives)};selected={len(selected)};"
                f"verified={len(task_evidence)};"
                f"pages={query_meta.get('pages_fetched')};"
                f"partial_reasons={','.join(partial_reasons) or 'none'};"
                f"nonblocking_failures={','.join(nonblocking_failures) or 'none'}"
            ),
        )]
        evidence_rows.extend(task_evidence)
        audit_rows.extend(task_audit)
        if audit_status == "OK":
            cache.set(key, {"evidence_rows": task_evidence, "audit_rows": task_audit})

    summary = {
        "company_event_task_count": task_count,
        "company_event_actual_fetch_count": network_fetches,
        "company_event_document_fetch_success_count": document_fetch_successes,
        "company_event_evidence_rows": len(evidence_rows),
        "company_event_active_count": sum(row.get("event_status") == "ACTIVE" for row in evidence_rows),
        "company_event_resolved_count": sum(row.get("event_status") == "RESOLVED" for row in evidence_rows),
        "company_event_failure_count": sum(row.get("status") == "FAILED" for row in audit_rows),
        "company_event_partial_count": sum(row.get("status") == "PARTIAL" for row in audit_rows),
    }
    return evidence_rows, audit_rows, summary
