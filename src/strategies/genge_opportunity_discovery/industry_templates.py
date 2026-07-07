"""Industry research task templates for opportunity discovery.

Templates are used to create evidence collection tasks only. They never make a
stock or an industry a candidate by themselves.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


DEFAULT_PUBLIC_SOURCES = [
    "国家统计局、发改委、工信部等政府公开数据",
    "交易所公告和上市公司公告",
    "行业协会、公开报价、公开研究摘要",
]

REQUIRED_INDUSTRIES = (
    "猪肉",
    "面板",
    "稀土",
    "有色",
    "化工",
    "钢铁",
    "煤炭",
    "光伏",
    "锂电",
    "半导体",
    "航运",
    "造纸",
    "玻璃",
    "水泥",
    "工程机械",
    "电力设备",
    "公用事业",
    "地产",
    "银行",
    "医药",
)

FALLBACK_INDICATORS = [
    {
        "name": "周期价格或量价指标",
        "description": "行业关键产品价格、销量、订单或景气度的公开变化",
        "direction_rule": "bottoming_or_recovery_is_positive",
        "positive_condition": "低位企稳、环比改善或同比降幅收窄",
        "negative_condition": "继续下行、库存累积或需求走弱",
        "source_hint": "行业协会、政府公开数据、公开报价、上市公司公告",
        "default_weight": 1.0,
        "freshness_limit_days": 60,
        "required_or_optional": "required",
    },
    {
        "name": "库存或产能状态",
        "description": "库存、产能利用率、供给纪律或出清进度",
        "direction_rule": "inventory_destocking_or_capacity_clearance_is_positive",
        "positive_condition": "库存去化、产能出清或供给纪律改善",
        "negative_condition": "库存上升、产能扩张或供给压力加大",
        "source_hint": "公开行业周报、公司公告、交易所披露",
        "default_weight": 1.0,
        "freshness_limit_days": 90,
        "required_or_optional": "required",
    },
    {
        "name": "利润或需求验证",
        "description": "价差、毛利、订单、终端需求或现金流改善",
        "direction_rule": "margin_or_demand_recovery_is_positive",
        "positive_condition": "利润修复或需求改善被公开数据交叉验证",
        "negative_condition": "利润继续恶化或终端需求继续走弱",
        "source_hint": "上市公司公告、交易所披露、政府公开数据",
        "default_weight": 0.9,
        "freshness_limit_days": 90,
        "required_or_optional": "optional",
    },
]


def indicator_templates_for(industry: str, schema: Mapping[str, Any] | None) -> tuple[List[Dict[str, Any]], str]:
    """Return indicator templates and support status for an industry."""

    industries = (schema or {}).get("industries") or {}
    config = industries.get(str(industry or "").strip()) or {}
    indicators = config.get("indicators") or []
    if indicators:
        return [dict(item) for item in indicators], "schema_supported"
    return [dict(item) for item in FALLBACK_INDICATORS], "unsupported_template"


def expected_industries(schema: Mapping[str, Any] | None, observed_industries: List[str]) -> List[str]:
    industries = set(REQUIRED_INDUSTRIES)
    industries.update(str(item).strip() for item in observed_industries if str(item).strip())
    industries.update(((schema or {}).get("industries") or {}).keys())
    return sorted(industries)
