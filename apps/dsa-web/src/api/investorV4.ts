import apiClient from './index';

export type InvestorV4Status = 'AVAILABLE_DATED_READ_ONLY' | 'UNAVAILABLE';
export type InvestorV4Delivery =
  | 'GITHUB_MAIN_READ'
  | 'LOCAL_DATED_FALLBACK'
  | 'LOCAL_DATED_ONLY'
  | 'UNAVAILABLE';

export type InvestorV4Holding = {
  code: string;
  name: string;
  last_reported_quantity?: number | null;
  frozen_reference_price?: number | null;
  reference_as_of?: string | null;
  recorded_formal_action?: string | null;
  executable_shares: 0;
  valuation_confidence?: string;
  value_range?: [number | null, number | null];
  reason_codes?: string | null;
};

export type InvestorV4Source = {
  path?: string;
  status?: string;
  sha256?: string;
  immutable_blob_url?: string;
};

export type InvestorV4Handoff = {
  contract_version: string;
  snapshot_id: string;
  generated_at: string;
  market_session_as_of: string;
  canonical_snapshot_id: string;
  canonical_source_run_id: string;
  no_auto_trade: true;
  blocking_reasons: string[];
  formal_buy_now: [];
  formal_wait_price: [];
  holdings: InvestorV4Holding[];
  holdings_truncated?: number;
  source_files: Record<string, InvestorV4Source>;
  feeds: {
    market_eod: { as_of: string; status: string; upstream_status?: string };
    funds?: { status: string };
    planning_cash?: { amount_cny: number | null; as_of?: string | null; status: string };
    broker_cash?: { amount_cny: null; status: string };
    executable_quotes?: { status: string };
    era_cycle?: { as_of?: string | null; status: string };
    official_issuer?: { status: string };
  };
  trend_research: {
    trend_id: string; lifecycle?: string; as_of?: string;
    authority: 'RESEARCH_ONLY';
  }[];
  research_audit?: {
    research_buy_count?: number;
    research_gap_count?: number;
    upstream_formal_buy_now_count?: number;
  };
};

export type InvestorV4DeliveryResponse = {
  status: InvestorV4Status;
  delivery: InvestorV4Delivery;
  retrieved_at: string;
  remote_manifest_blob_sha?: string | null;
  hand_off: InvestorV4Handoff | null;
  opening_decision_ready: false;
  execution_allowed: false;
  warnings: string[];
};

export const investorV4Api = {
  async latest(): Promise<InvestorV4DeliveryResponse> {
    const { data } = await apiClient.get<InvestorV4DeliveryResponse>('/investor-v4/latest', {
      headers: { 'Cache-Control': 'no-cache' },
    });
    return data;
  },
};
