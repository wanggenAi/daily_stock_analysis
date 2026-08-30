"""Source registry for Era Radar collectors.

This is a policy registry, not a fetch implementation. It defines which source classes may
contribute to which evidence families and their default trust tier.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    family: str
    tier: str
    scope: str
    description: str


DEFAULT_SOURCE_REGISTRY = (
    SourceSpec("china_state_council", "POLICY_CAPITAL", "OFFICIAL", "CN", "State Council policy and implementation documents"),
    SourceSpec("ndrc", "POLICY_CAPITAL", "OFFICIAL", "CN", "NDRC plans, approvals and industrial policy"),
    SourceSpec("miit", "POLICY_CAPITAL", "OFFICIAL", "CN", "MIIT industrial policy, standards and sector plans"),
    SourceSpec("mof", "POLICY_CAPITAL", "OFFICIAL", "CN", "Ministry of Finance expenditure and fiscal support evidence"),
    SourceSpec("pbc", "FINANCIAL_CAPITAL", "OFFICIAL", "CN", "PBOC aggregate financing and monetary/credit structure"),
    SourceSpec("stats_cn", "REAL_DEMAND", "OFFICIAL", "CN", "National Bureau of Statistics demand, output, population and investment series"),
    SourceSpec("customs_cn", "REAL_DEMAND", "OFFICIAL", "CN", "China customs trade flows"),
    SourceSpec("sse_szse_disclosures", "INDUSTRIAL_CAPITAL", "PRIMARY", "CN", "Listed-company capex, orders, projects and strategic investment disclosures"),
    SourceSpec("company_reports", "INDUSTRIAL_CAPITAL", "PRIMARY", "GLOBAL", "Company annual/interim reports and presentations"),
    SourceSpec("patents_standards", "TECHNOLOGY", "PRIMARY", "GLOBAL", "Patent, standards and technical-readiness evidence"),
    SourceSpec("iea", "GLOBAL_STRUCTURE", "HIGH_QUALITY_SECONDARY", "GLOBAL", "Energy system demand, capacity and transition datasets"),
    SourceSpec("world_bank", "GLOBAL_STRUCTURE", "HIGH_QUALITY_SECONDARY", "GLOBAL", "Demographic, development and structural economic data"),
    SourceSpec("un_data", "GLOBAL_STRUCTURE", "HIGH_QUALITY_SECONDARY", "GLOBAL", "Population and long-duration structural datasets"),
)


def sources_for_family(family: str) -> tuple[SourceSpec, ...]:
    return tuple(item for item in DEFAULT_SOURCE_REGISTRY if item.family == family)
