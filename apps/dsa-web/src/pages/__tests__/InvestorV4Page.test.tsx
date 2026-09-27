import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { investorV4Api } from '../../api/investorV4';
import type { InvestorV4DeliveryResponse } from '../../api/investorV4';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import InvestorV4Page from '../InvestorV4Page';

vi.mock('../../api/investorV4', () => ({
  investorV4Api: { latest: vi.fn() },
}));

const originalUrl = 'https://api.github.com/repos/example/repo/git/blobs/' + 'a'.repeat(40);

const stale: InvestorV4DeliveryResponse = {
  status: 'AVAILABLE_DATED_READ_ONLY',
  delivery: 'GITHUB_MAIN_READ',
  retrieved_at: '2026-09-28T00:01:00Z',
  opening_decision_ready: false,
  execution_allowed: false,
  warnings: [],
  hand_off: {
    contract_version: 'GEN_GE_INVESTOR_CHATGPT_HANDOFF_V1',
    snapshot_id: 'snap-1',
    canonical_snapshot_id: 'canonical-1',
    canonical_source_run_id: '100',
    generated_at: '2026-09-28T00:00:00Z',
    market_session_as_of: '2026-09-24',
    no_auto_trade: true,
    blocking_reasons: ['STALE_OR_UNVERIFIED_MARKET_SESSION'],
    formal_buy_now: [],
    formal_wait_price: [],
    holdings: [{
      code: '600406', name: '国电南瑞',
      last_reported_quantity: 200,
      frozen_reference_price: 22.27,
      recorded_formal_action: 'REDUCE_25',
      reference_as_of: '2026-09-24',
      executable_shares: 0,
      value_range: [12.83, 26.08],
      valuation_confidence: 'HIGH',
    }],
    source_files: {
      dashboard: {
        path: 'data/investor_decision_dashboard/latest.json',
        sha256: 'b'.repeat(64),
        immutable_blob_url: originalUrl,
      },
    },
    feeds: {
      market_eod: { as_of: '2026-09-24', status: 'STALE_OR_UNVERIFIED' },
      funds: { status: 'UNVERIFIED' },
      planning_cash: { as_of: '2026-09-20', amount_cny: 50000, status: 'DATED_PLANNING_ONLY' },
      broker_cash: { amount_cny: null, status: 'UNKNOWN' },
      executable_quotes: { status: 'UNVERIFIED' },
    },
    trend_research: [{
      trend_id: 'electrification_infrastructure', lifecycle: 'EMERGING',
      as_of: '2026-09-20', authority: 'RESEARCH_ONLY',
    }],
    research_audit: { research_buy_count: 1, research_gap_count: 18 },
  },
};

function show() {
  return render(
    <UiLanguageProvider>
      <InvestorV4Page />
    </UiLanguageProvider>,
  );
}

describe('InvestorV4Page historical-only web source', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.mocked(investorV4Api.latest).mockResolvedValue(stale);
  });

  it('shows market as-of not generated-at as usable trading data', async () => {
    show();
    expect(await screen.findByText('2026-09-24', { selector: 'p.font-semibold' })).toBeTruthy();
    expect(screen.getByText('非当前可执行行情')).toBeTruthy();
    expect(screen.getByText('当前可验证立即买单：0')).toBeTruthy();
    expect(screen.getByText('原记录动作: REDUCE_25')).toBeTruthy();
    expect(screen.getByText('研究线索（非正式交易权限）: 1')).toBeTruthy();
    expect(screen.getByText('券商实时现金: 未验证')).toBeTruthy();
    const links = screen.getAllByRole('link', { name: /发布时原始报告|完整来源链接/ });
    expect(links).toHaveLength(2);
    expect(links[0].getAttribute('href')).toBe(originalUrl);
  });

  it('never automatically calls ChatGPT and only copies on direct user click', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true, value: { writeText },
    });
    show();
    await screen.findByText('已读取 GitHub main 交接清单');
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /复制 ChatGPT/ }));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('link', { name: /主动打开 ChatGPT/ }).getAttribute('href'))
      .toBe('https://chatgpt.com/');
  });

  it('unavailable H1 does not invent a price or action', async () => {
    vi.mocked(investorV4Api.latest).mockResolvedValue({
      ...stale, status: 'UNAVAILABLE', hand_off: null,
      delivery: 'UNAVAILABLE', warnings: ['NO_VERIFIED_H1_MANIFEST'],
    });
    show();
    expect(await screen.findByText('尚无可用的 H1 交接产物')).toBeTruthy();
    expect(screen.getByText('当前可验证立即买单：0')).toBeTruthy();
    expect(screen.queryByText('22.27')).toBeNull();
  });

  it('shows local fallback as unverified remote freshness', async () => {
    vi.mocked(investorV4Api.latest).mockResolvedValue({
      ...stale, delivery: 'LOCAL_DATED_FALLBACK',
      warnings: ['GITHUB_MAIN_UNAVAILABLE_OR_INVALID'],
    });
    show();
    await screen.findByText(/仅已部署的历史快照/);
    expect(screen.getByText(/GITHUB_MAIN_UNAVAILABLE_OR_INVALID/)).toBeTruthy();
  });
});
