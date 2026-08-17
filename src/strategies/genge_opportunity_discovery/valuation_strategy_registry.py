"""Deterministic company-archetype routing for valuation research.

This is an orchestration layer, not a valuation model. It organizes the
specialized model modules already present in ``genge_opportunity_discovery``
behind an immutable registry and conservative, table-driven routing rules.

The design intentionally uses a small subset of GoF ideas where they solve a
real problem:

* Strategy/Registry: model families are discoverable without a growing
  production ``if/elif`` tree.
* Adapter-ready descriptors: existing pure model modules remain unchanged.
* Composite routing: a company may need a normalizer followed by a valuation
  model (capacity-cycle normalization + reverse earnings, for example).
* Open/Closed routing table: a new archetype/rule can be added without changing
  the report pipeline.

A descriptor only says whether a strategy normalizes evidence or performs a
valuation. Whether a valuation is primary or an alternative is route-specific;
``ValuationRouteDecision.primary_strategy_id`` owns that decision. This avoids
encoding a context-dependent role in a globally shared strategy descriptor.

Routing metadata is research-only. It cannot create a Formal BUY, change
position sizing, bypass hard risk gates, or trigger automatic trading.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum


class CompanyArchetype(str, Enum):
    GENERAL_EARNINGS = "GENERAL_EARNINGS"
    BANK = "BANK"
    INSURANCE = "INSURANCE"
    CAPITAL_MARKETS = "CAPITAL_MARKETS"
    REAL_ESTATE_NAV = "REAL_ESTATE_NAV"
    BIOTECH_RNPV = "BIOTECH_RNPV"
    CONSUMER_COMPOUNDER = "CONSUMER_COMPOUNDER"
    BIOLOGICAL_CYCLE = "BIOLOGICAL_CYCLE"
    CAPACITY_CYCLE = "CAPACITY_CYCLE"
    PRODUCT_CYCLE = "PRODUCT_CYCLE"
    TRANSPORT_CYCLE = "TRANSPORT_CYCLE"
    YIELD_ASSET = "YIELD_ASSET"


class StrategyRole(str, Enum):
    NORMALIZER = "NORMALIZER"
    VALUATION = "VALUATION"


@dataclass(frozen=True)
class StrategyDescriptor:
    strategy_id: str
    archetype: CompanyArchetype
    role: StrategyRole
    module_path: str
    execution_order: int
    pe_based: bool
    description: str


@dataclass(frozen=True)
class StrategySelection:
    strategy_id: str
    archetype: CompanyArchetype
    role: StrategyRole
    module_path: str
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy_id": self.strategy_id,
            "archetype": self.archetype.value,
            "role": self.role.value,
            "module_path": self.module_path,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ValuationRouteDecision:
    archetypes: tuple[CompanyArchetype, ...]
    selections: tuple[StrategySelection, ...]
    primary_strategy_id: str
    routing_confidence: float
    status: str
    reasons: tuple[str, ...]

    @property
    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(item.strategy_id for item in self.selections)

    @property
    def valuation_strategy_ids(self) -> tuple[str, ...]:
        return tuple(
            item.strategy_id
            for item in self.selections
            if item.role == StrategyRole.VALUATION
        )

    @property
    def alternative_strategy_ids(self) -> tuple[str, ...]:
        return tuple(
            item for item in self.valuation_strategy_ids if item != self.primary_strategy_id
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "archetypes": [item.value for item in self.archetypes],
            "strategy_ids": list(self.strategy_ids),
            "valuation_strategy_ids": list(self.valuation_strategy_ids),
            "primary_strategy_id": self.primary_strategy_id,
            "alternative_strategy_ids": list(self.alternative_strategy_ids),
            "routing_confidence": self.routing_confidence,
            "status": self.status,
            "reasons": list(self.reasons),
            "selections": [item.to_dict() for item in self.selections],
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


class ValuationStrategyRegistry:
    """Immutable registry of valuation/normalization strategy descriptors."""

    def __init__(self, strategies: Iterable[StrategyDescriptor]):
        ordered = tuple(
            sorted(strategies, key=lambda item: (item.execution_order, item.strategy_id))
        )
        ids = [item.strategy_id for item in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate valuation strategy_id")
        if any(not item.strategy_id.strip() for item in ordered):
            raise ValueError("valuation strategy_id must be non-empty")
        self._strategies = ordered
        self._by_id = {item.strategy_id: item for item in ordered}

    @property
    def strategies(self) -> tuple[StrategyDescriptor, ...]:
        return self._strategies

    def get(self, strategy_id: str) -> StrategyDescriptor:
        return self._by_id[str(strategy_id)]

    def for_archetypes(
        self,
        archetypes: Iterable[CompanyArchetype],
    ) -> tuple[StrategyDescriptor, ...]:
        wanted = set(archetypes)
        return tuple(item for item in self._strategies if item.archetype in wanted)

    def with_strategy(self, strategy: StrategyDescriptor) -> "ValuationStrategyRegistry":
        """Return an extended registry without mutating the shared default."""

        return ValuationStrategyRegistry((*self._strategies, strategy))


DEFAULT_STRATEGIES = (
    StrategyDescriptor(
        "biological_cycle_normalizer",
        CompanyArchetype.BIOLOGICAL_CYCLE,
        StrategyRole.NORMALIZER,
        "src.strategies.genge_opportunity_discovery.biological_cycle_normalization",
        10,
        False,
        "Normalize biological/animal-production cycle earnings before valuation.",
    ),
    StrategyDescriptor(
        "capacity_cycle_normalizer",
        CompanyArchetype.CAPACITY_CYCLE,
        StrategyRole.NORMALIZER,
        "src.strategies.genge_opportunity_discovery.capacity_cycle_normalization",
        10,
        False,
        "Normalize commodity/capacity-cycle economics before valuation.",
    ),
    StrategyDescriptor(
        "product_cycle_normalizer",
        CompanyArchetype.PRODUCT_CYCLE,
        StrategyRole.NORMALIZER,
        "src.strategies.genge_opportunity_discovery.product_cycle_normalization",
        10,
        False,
        "Normalize product/technology-cycle earnings before valuation.",
    ),
    StrategyDescriptor(
        "bank_residual_income",
        CompanyArchetype.BANK,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.bank_valuation",
        100,
        False,
        "Common-equity P/B and sustainable-ROE residual-income bridge for banks.",
    ),
    StrategyDescriptor(
        "insurance_embedded_value",
        CompanyArchetype.INSURANCE,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.insurance_valuation",
        100,
        False,
        "Embedded-value/new-business-value appraisal bridge for insurers.",
    ),
    StrategyDescriptor(
        "capital_markets_cycle",
        CompanyArchetype.CAPITAL_MARKETS,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.capital_markets_valuation",
        100,
        False,
        "Cycle-aware valuation for brokers and capital-markets businesses.",
    ),
    StrategyDescriptor(
        "real_estate_nav",
        CompanyArchetype.REAL_ESTATE_NAV,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.real_estate_nav_valuation",
        100,
        False,
        "Project-NAV valuation for property developers.",
    ),
    StrategyDescriptor(
        "biotech_rnpv",
        CompanyArchetype.BIOTECH_RNPV,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.biotech_rnpv_valuation",
        100,
        False,
        "Probability-adjusted pipeline rNPV and financing-runway valuation.",
    ),
    StrategyDescriptor(
        "consumer_compounder_dcf",
        CompanyArchetype.CONSUMER_COMPOUNDER,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.consumer_compounder_valuation",
        100,
        False,
        "Owner-earnings DCF with explicit growth duration for durable compounders.",
    ),
    StrategyDescriptor(
        "transport_cycle",
        CompanyArchetype.TRANSPORT_CYCLE,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.transport_cycle_valuation",
        100,
        False,
        "Through-cycle EV bridge for shipping/airline-style transport businesses.",
    ),
    StrategyDescriptor(
        "yield_asset",
        CompanyArchetype.YIELD_ASSET,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.yield_asset_valuation",
        100,
        False,
        "FCFE/yield valuation for mature regulated or long-lived yield assets.",
    ),
    StrategyDescriptor(
        "general_reverse_earnings",
        CompanyArchetype.GENERAL_EARNINGS,
        StrategyRole.VALUATION,
        "src.strategies.genge_opportunity_discovery.fundamental_valuation",
        110,
        True,
        "Generic normalized-earnings reverse valuation and expectation-gap bridge.",
    ),
)

DEFAULT_VALUATION_STRATEGY_REGISTRY = ValuationStrategyRegistry(DEFAULT_STRATEGIES)


@dataclass(frozen=True)
class RouteRule:
    rule_id: str
    industry_tokens: tuple[str, ...]
    archetypes: tuple[CompanyArchetype, ...]
    confidence: float
    status: str
    include_general: bool = False


# Ordered from narrow/specialized to broader cycle families. Airport/port are
# yield assets, not transport-cycle EV names: transport_cycle_valuation itself
# explicitly reserves that bridge for businesses such as shipping and airlines.
# ``航空`` alone is intentionally absent because it would also match aerospace
# manufacturing labels such as 航空装备/航空航天. Real-estate NAV similarly
# requires explicit developer semantics rather than any label containing 地产.
INDUSTRY_ROUTE_RULES = (
    RouteRule(
        "insurance_industry",
        ("保险",),
        (CompanyArchetype.INSURANCE,),
        0.95,
        "SPECIALIZED_EXCLUSIVE",
    ),
    RouteRule(
        "capital_markets_industry",
        ("证券", "券商", "资本市场"),
        (CompanyArchetype.CAPITAL_MARKETS,),
        0.95,
        "SPECIALIZED_EXCLUSIVE",
    ),
    RouteRule(
        "bank_industry",
        ("银行",),
        (CompanyArchetype.BANK,),
        0.95,
        "SPECIALIZED_EXCLUSIVE",
    ),
    RouteRule(
        "real_estate_developer",
        ("房地产开发", "地产开发", "住宅开发", "房屋开发"),
        (CompanyArchetype.REAL_ESTATE_NAV,),
        0.95,
        "SPECIALIZED_EXCLUSIVE",
    ),
    RouteRule(
        "transport_cycle_industry",
        ("航运", "航空运输", "航空公司", "航空客运", "航空货运"),
        (CompanyArchetype.TRANSPORT_CYCLE,),
        0.88,
        "SPECIALIZED_PRIMARY",
    ),
    RouteRule(
        "yield_asset_industry",
        ("机场", "港口", "公用事业", "水务", "燃气", "电力运营", "高速公路"),
        (CompanyArchetype.YIELD_ASSET,),
        0.84,
        "SPECIALIZED_PRIMARY",
    ),
    RouteRule(
        "biological_cycle_industry",
        ("猪肉", "生猪", "养殖", "畜牧"),
        (CompanyArchetype.BIOLOGICAL_CYCLE,),
        0.90,
        "NORMALIZED_GENERIC",
        True,
    ),
    RouteRule(
        "capacity_or_commodity_cycle_industry",
        ("稀土", "稀有金属", "有色", "贵金属", "化工", "钢铁", "煤炭", "玻璃", "水泥", "造纸"),
        (CompanyArchetype.CAPACITY_CYCLE,),
        0.85,
        "NORMALIZED_GENERIC",
        True,
    ),
    RouteRule(
        "technology_capacity_cycle_industry",
        ("面板", "光伏", "锂电"),
        (CompanyArchetype.CAPACITY_CYCLE,),
        0.82,
        "NORMALIZED_GENERIC",
        True,
    ),
    RouteRule(
        "product_cycle_industry",
        ("半导体", "消费电子", "电子元件", "显示器件"),
        (CompanyArchetype.PRODUCT_CYCLE,),
        0.80,
        "NORMALIZED_GENERIC",
        True,
    ),
)


_EXPLICIT_ALIASES = {
    "general": CompanyArchetype.GENERAL_EARNINGS,
    "general_earnings": CompanyArchetype.GENERAL_EARNINGS,
    "通用盈利": CompanyArchetype.GENERAL_EARNINGS,
    "bank": CompanyArchetype.BANK,
    "银行": CompanyArchetype.BANK,
    "insurance": CompanyArchetype.INSURANCE,
    "保险": CompanyArchetype.INSURANCE,
    "capital_markets": CompanyArchetype.CAPITAL_MARKETS,
    "券商": CompanyArchetype.CAPITAL_MARKETS,
    "证券": CompanyArchetype.CAPITAL_MARKETS,
    "real_estate_nav": CompanyArchetype.REAL_ESTATE_NAV,
    "地产": CompanyArchetype.REAL_ESTATE_NAV,
    "房地产": CompanyArchetype.REAL_ESTATE_NAV,
    "biotech_rnpv": CompanyArchetype.BIOTECH_RNPV,
    "创新药": CompanyArchetype.BIOTECH_RNPV,
    "biotech": CompanyArchetype.BIOTECH_RNPV,
    "consumer_compounder": CompanyArchetype.CONSUMER_COMPOUNDER,
    "消费复利": CompanyArchetype.CONSUMER_COMPOUNDER,
    "biological_cycle": CompanyArchetype.BIOLOGICAL_CYCLE,
    "生物周期": CompanyArchetype.BIOLOGICAL_CYCLE,
    "capacity_cycle": CompanyArchetype.CAPACITY_CYCLE,
    "产能周期": CompanyArchetype.CAPACITY_CYCLE,
    "product_cycle": CompanyArchetype.PRODUCT_CYCLE,
    "产品周期": CompanyArchetype.PRODUCT_CYCLE,
    "transport_cycle": CompanyArchetype.TRANSPORT_CYCLE,
    "运输周期": CompanyArchetype.TRANSPORT_CYCLE,
    "yield_asset": CompanyArchetype.YIELD_ASSET,
    "收益资产": CompanyArchetype.YIELD_ASSET,
}


def _tokens(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = value.replace("；", ";").replace("，", ",").replace("|", ",")
        parts: list[str] = []
        for segment in raw.split(";"):
            parts.extend(segment.split(","))
        return tuple(item.strip().lower() for item in parts if item.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(item).strip().lower() for item in value if str(item).strip())
    text = str(value).strip().lower()
    return (text,) if text else ()


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    return any(token in text for token in tokens)


def _explicit_archetypes(hints: object) -> tuple[CompanyArchetype, ...]:
    result: list[CompanyArchetype] = []
    for hint in _tokens(hints):
        archetype = _EXPLICIT_ALIASES.get(hint)
        if archetype is None:
            try:
                archetype = CompanyArchetype(hint.upper())
            except ValueError:
                continue
        if archetype not in result:
            result.append(archetype)
    return tuple(result)


def _industry_rule(industry: object, business_tags: object = None) -> RouteRule | None:
    text = " ".join(
        item
        for item in (str(industry or "").strip().lower(), " ".join(_tokens(business_tags)))
        if item
    )
    for rule in INDUSTRY_ROUTE_RULES:
        if _contains_any(text, rule.industry_tokens):
            return rule
    return None


def _inferred_route(
    industry: object,
    business_tags: object,
) -> tuple[list[CompanyArchetype], float, str, str]:
    tag_text = " ".join(_tokens(business_tags))

    # Generic 医药 is deliberately insufficient evidence for pipeline rNPV.
    if _contains_any(
        tag_text,
        ("创新药", "创新生物药", "biotech", "pipeline-driven", "临床管线", "研发管线"),
    ):
        return (
            [CompanyArchetype.BIOTECH_RNPV],
            0.95,
            "SPECIALIZED_EXCLUSIVE",
            "business_tag_indicates_pipeline_driven_biotech",
        )

    if _contains_any(tag_text, ("品牌消费", "消费龙头", "稳定复利", "consumer compounder")):
        return (
            [CompanyArchetype.CONSUMER_COMPOUNDER, CompanyArchetype.GENERAL_EARNINGS],
            0.78,
            "SPECIALIZED_WITH_GENERIC_ALTERNATIVE",
            "compounder_business_tag",
        )

    rule = _industry_rule(industry, business_tags)
    if rule is not None:
        archetypes = list(rule.archetypes)
        if rule.include_general:
            archetypes.append(CompanyArchetype.GENERAL_EARNINGS)
        return archetypes, rule.confidence, rule.status, rule.rule_id

    confidence = 0.50 if str(industry or "").strip() else 0.35
    return (
        [CompanyArchetype.GENERAL_EARNINGS],
        confidence,
        "GENERIC_FALLBACK",
        "no_safe_specialized_archetype_match",
    )


def route_valuation_strategies(
    *,
    industry: object = None,
    business_tags: object = None,
    archetype_hints: object = None,
    registry: ValuationStrategyRegistry = DEFAULT_VALUATION_STRATEGY_REGISTRY,
) -> ValuationRouteDecision:
    """Select a deterministic research model pipeline for one company.

    Explicit hints have highest confidence, but they still cannot bypass model
    input validation. A hinted normalizer automatically receives the generic
    valuation bridge unless another valuation family was also explicitly
    selected.
    """

    explicit = _explicit_archetypes(archetype_hints)
    if explicit:
        archetypes = list(explicit)
        descriptors = registry.for_archetypes(archetypes)
        has_valuation = any(item.role == StrategyRole.VALUATION for item in descriptors)
        if not has_valuation and CompanyArchetype.GENERAL_EARNINGS not in archetypes:
            archetypes.append(CompanyArchetype.GENERAL_EARNINGS)
        confidence = 1.0
        status = "EXPLICIT_ARCHETYPE_ROUTE"
        reason = "explicit_archetype_hint"
    else:
        archetypes, confidence, status, reason = _inferred_route(industry, business_tags)

    descriptors = registry.for_archetypes(archetypes)
    selections = tuple(
        StrategySelection(
            strategy_id=item.strategy_id,
            archetype=item.archetype,
            role=item.role,
            module_path=item.module_path,
            confidence=confidence,
            reason=reason,
        )
        for item in descriptors
    )
    primary = next(
        (item.strategy_id for item in selections if item.role == StrategyRole.VALUATION),
        "",
    )
    if not primary:
        raise ValueError("valuation route must contain a valuation strategy")

    ordered_archetypes: list[CompanyArchetype] = []
    for selection in selections:
        if selection.archetype not in ordered_archetypes:
            ordered_archetypes.append(selection.archetype)

    return ValuationRouteDecision(
        archetypes=tuple(ordered_archetypes),
        selections=selections,
        primary_strategy_id=primary,
        routing_confidence=confidence,
        status=status,
        reasons=(reason,),
    )
