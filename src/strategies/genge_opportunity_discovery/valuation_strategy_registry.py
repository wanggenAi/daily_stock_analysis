"""Deterministic company-archetype routing for valuation research.

This module is an orchestration layer, not a valuation model.  It organizes the
specialized models that already exist in ``genge_opportunity_discovery`` behind
an immutable registry and a conservative router.

Design goals:

* Strategy/Registry: valuation families are discoverable without a growing
  ``if/elif`` tree in the report pipeline.
* Adapter-ready descriptors: existing pure model modules remain unchanged and
  can be wrapped/executed by later adapters.
* Composite routing: one company may require a normalizer plus a valuation
  model (for example capacity-cycle normalization followed by the generic
  reverse-earnings bridge).
* Fail-safe routing: industry labels only select models when the mapping is
  economically explicit.  Ambiguous industries fall back to the generic
  research model; generic ``医药`` never implies biotech rNPV by itself.
* Auditability: every decision carries the selected strategies, confidence and
  human-readable reasons.

Routing metadata is research-only.  It cannot create a Formal BUY, change
position sizing, bypass hard risk gates, or trigger automatic trading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


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
    PRIMARY_VALUATION = "PRIMARY_VALUATION"
    ALTERNATIVE_VALUATION = "ALTERNATIVE_VALUATION"


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
        return tuple(selection.strategy_id for selection in self.selections)

    def to_dict(self) -> dict[str, object]:
        return {
            "archetypes": [item.value for item in self.archetypes],
            "strategy_ids": list(self.strategy_ids),
            "primary_strategy_id": self.primary_strategy_id,
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
            sorted(
                strategies,
                key=lambda item: (item.execution_order, item.strategy_id),
            )
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
        strategy_id="biological_cycle_normalizer",
        archetype=CompanyArchetype.BIOLOGICAL_CYCLE,
        role=StrategyRole.NORMALIZER,
        module_path="src.strategies.genge_opportunity_discovery.biological_cycle_normalization",
        execution_order=10,
        pe_based=False,
        description="Normalize biological/animal-production cycle earnings before valuation.",
    ),
    StrategyDescriptor(
        strategy_id="capacity_cycle_normalizer",
        archetype=CompanyArchetype.CAPACITY_CYCLE,
        role=StrategyRole.NORMALIZER,
        module_path="src.strategies.genge_opportunity_discovery.capacity_cycle_normalization",
        execution_order=10,
        pe_based=False,
        description="Normalize commodity/capacity-cycle economics before valuation.",
    ),
    StrategyDescriptor(
        strategy_id="product_cycle_normalizer",
        archetype=CompanyArchetype.PRODUCT_CYCLE,
        role=StrategyRole.NORMALIZER,
        module_path="src.strategies.genge_opportunity_discovery.product_cycle_normalization",
        execution_order=10,
        pe_based=False,
        description="Normalize product/technology cycle earnings before valuation.",
    ),
    StrategyDescriptor(
        strategy_id="bank_residual_income",
        archetype=CompanyArchetype.BANK,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.bank_valuation",
        execution_order=100,
        pe_based=False,
        description="Common-equity P/B and sustainable-ROE residual-income bridge for banks.",
    ),
    StrategyDescriptor(
        strategy_id="insurance_embedded_value",
        archetype=CompanyArchetype.INSURANCE,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.insurance_valuation",
        execution_order=100,
        pe_based=False,
        description="Insurance-specific valuation bridge rather than industrial P/E.",
    ),
    StrategyDescriptor(
        strategy_id="capital_markets_cycle",
        archetype=CompanyArchetype.CAPITAL_MARKETS,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.capital_markets_valuation",
        execution_order=100,
        pe_based=False,
        description="Cycle-aware valuation for brokers and capital-markets businesses.",
    ),
    StrategyDescriptor(
        strategy_id="real_estate_nav",
        archetype=CompanyArchetype.REAL_ESTATE_NAV,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.real_estate_nav_valuation",
        execution_order=100,
        pe_based=False,
        description="Asset/NAV-oriented valuation for property developers and operators.",
    ),
    StrategyDescriptor(
        strategy_id="biotech_rnpv",
        archetype=CompanyArchetype.BIOTECH_RNPV,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.biotech_rnpv_valuation",
        execution_order=100,
        pe_based=False,
        description="Probability-adjusted pipeline rNPV and financing-runway valuation.",
    ),
    StrategyDescriptor(
        strategy_id="consumer_compounder_dcf",
        archetype=CompanyArchetype.CONSUMER_COMPOUNDER,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.consumer_compounder_valuation",
        execution_order=100,
        pe_based=False,
        description="Owner-earnings DCF with explicit growth duration for durable compounders.",
    ),
    StrategyDescriptor(
        strategy_id="transport_cycle",
        archetype=CompanyArchetype.TRANSPORT_CYCLE,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.transport_cycle_valuation",
        execution_order=100,
        pe_based=False,
        description="Transport/shipping cycle-specific valuation.",
    ),
    StrategyDescriptor(
        strategy_id="yield_asset",
        archetype=CompanyArchetype.YIELD_ASSET,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.yield_asset_valuation",
        execution_order=100,
        pe_based=False,
        description="Cash-yield/asset valuation for mature regulated or yield-like assets.",
    ),
    StrategyDescriptor(
        strategy_id="general_reverse_earnings",
        archetype=CompanyArchetype.GENERAL_EARNINGS,
        role=StrategyRole.PRIMARY_VALUATION,
        module_path="src.strategies.genge_opportunity_discovery.fundamental_valuation",
        execution_order=110,
        pe_based=True,
        description="Generic normalized-earnings reverse valuation and expectation-gap bridge.",
    ),
)

DEFAULT_VALUATION_STRATEGY_REGISTRY = ValuationStrategyRegistry(DEFAULT_STRATEGIES)


@dataclass(frozen=True)
class _RouteSpec:
    archetypes: tuple[CompanyArchetype, ...]
    confidence: float
    status: str
    include_general: bool
    reason: str


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
        pieces: list[str] = []
        for semi in raw.split(";"):
            pieces.extend(semi.split(","))
        return tuple(item.strip().lower() for item in pieces if item.strip())
    if isinstance(value, Sequence):
        return tuple(str(item).strip().lower() for item in value if str(item).strip())
    return (str(value).strip().lower(),) if str(value).strip() else ()


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


def _spec_from_industry_and_tags(industry: object, business_tags: object) -> _RouteSpec:
    industry_text = str(industry or "").strip().lower()
    tag_text = " ".join(_tokens(business_tags))
    combined = f"{industry_text} {tag_text}".strip()

    # Pipeline-driven biotech is intentionally tag/hint driven. Generic 医药 is
    # too broad and must not be silently converted into an rNPV company.
    if _contains_any(tag_text, ("创新药", "创新生物药", "biotech", "pipeline-driven", "临床管线", "研发管线")):
        return _RouteSpec(
            (CompanyArchetype.BIOTECH_RNPV,),
            0.95,
            "SPECIALIZED_EXCLUSIVE",
            False,
            "business_tag_indicates_pipeline_driven_biotech",
        )

    if _contains_any(industry_text, ("保险",)):
        return _RouteSpec((CompanyArchetype.INSURANCE,), 0.95, "SPECIALIZED_EXCLUSIVE", False, "insurance_industry")
    if _contains_any(industry_text, ("证券", "券商", "资本市场")):
        return _RouteSpec((CompanyArchetype.CAPITAL_MARKETS,), 0.95, "SPECIALIZED_EXCLUSIVE", False, "capital_markets_industry")
    if _contains_any(industry_text, ("银行",)):
        return _RouteSpec((CompanyArchetype.BANK,), 0.95, "SPECIALIZED_EXCLUSIVE", False, "bank_industry")
    if _contains_any(industry_text, ("房地产", "地产")):
        return _RouteSpec((CompanyArchetype.REAL_ESTATE_NAV,), 0.9, "SPECIALIZED_EXCLUSIVE", False, "real_estate_industry")
    if _contains_any(industry_text, ("航运", "航空", "机场", "港口")):
        return _RouteSpec((CompanyArchetype.TRANSPORT_CYCLE,), 0.88, "SPECIALIZED_PRIMARY", False, "transport_cycle_industry")
    if _contains_any(industry_text, ("公用事业", "水务", "燃气", "电力运营", "高速公路")):
        return _RouteSpec((CompanyArchetype.YIELD_ASSET,), 0.82, "SPECIALIZED_PRIMARY", False, "yield_asset_industry")
    if _contains_any(industry_text, ("猪肉", "生猪", "养殖", "畜牧")):
        return _RouteSpec((CompanyArchetype.BIOLOGICAL_CYCLE,), 0.9, "NORMALIZED_GENERIC", True, "biological_cycle_industry")
    if _contains_any(industry_text, ("稀土", "稀有金属", "有色", "贵金属", "化工", "钢铁", "煤炭", "玻璃", "水泥", "造纸")):
        return _RouteSpec((CompanyArchetype.CAPACITY_CYCLE,), 0.85, "NORMALIZED_GENERIC", True, "capacity_or_commodity_cycle_industry")
    if _contains_any(industry_text, ("面板", "光伏", "锂电")):
        return _RouteSpec((CompanyArchetype.CAPACITY_CYCLE,), 0.82, "NORMALIZED_GENERIC", True, "technology_capacity_cycle_industry")
    if _contains_any(industry_text, ("半导体", "消费电子", "电子元件", "显示器件")):
        return _RouteSpec((CompanyArchetype.PRODUCT_CYCLE,), 0.8, "NORMALIZED_GENERIC", True, "product_cycle_industry")
    if _contains_any(combined, ("品牌消费", "消费龙头", "稳定复利", "consumer compounder")):
        return _RouteSpec((CompanyArchetype.CONSUMER_COMPOUNDER,), 0.78, "SPECIALIZED_WITH_GENERIC_ALTERNATIVE", True, "compounder_business_tag")

    return _RouteSpec(
        (CompanyArchetype.GENERAL_EARNINGS,),
        0.5 if industry_text else 0.35,
        "GENERIC_FALLBACK",
        False,
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

    Explicit archetype hints are highest-confidence research metadata.  They do
    not bypass model input validation: the eventual model adapter must still
    fail closed when its required evidence is missing.
    """

    explicit = _explicit_archetypes(archetype_hints)
    if explicit:
        archetypes = list(explicit)
        # Normalizers require a downstream valuation bridge. Add the generic
        # bridge unless the caller explicitly supplied another valuation family.
        descriptors = registry.for_archetypes(archetypes)
        has_valuation = any(item.role != StrategyRole.NORMALIZER for item in descriptors)
        if not has_valuation and CompanyArchetype.GENERAL_EARNINGS not in archetypes:
            archetypes.append(CompanyArchetype.GENERAL_EARNINGS)
        confidence = 1.0
        status = "EXPLICIT_ARCHETYPE_ROUTE"
        base_reason = "explicit_archetype_hint"
    else:
        spec = _spec_from_industry_and_tags(industry, business_tags)
        archetypes = list(spec.archetypes)
        if spec.include_general and CompanyArchetype.GENERAL_EARNINGS not in archetypes:
            archetypes.append(CompanyArchetype.GENERAL_EARNINGS)
        confidence = spec.confidence
        status = spec.status
        base_reason = spec.reason

    descriptors = registry.for_archetypes(archetypes)
    selections = tuple(
        StrategySelection(
            strategy_id=item.strategy_id,
            archetype=item.archetype,
            role=item.role,
            module_path=item.module_path,
            confidence=confidence,
            reason=base_reason,
        )
        for item in descriptors
    )
    primary = next(
        (
            item.strategy_id
            for item in selections
            if item.role in {StrategyRole.PRIMARY_VALUATION, StrategyRole.ALTERNATIVE_VALUATION}
        ),
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
        reasons=(base_reason,),
    )
