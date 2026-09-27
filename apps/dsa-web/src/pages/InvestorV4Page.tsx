import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, ClipboardCopy, RefreshCw, ShieldAlert } from 'lucide-react';
import { investorV4Api } from '../api/investorV4';
import type { InvestorV4DeliveryResponse, InvestorV4Holding } from '../api/investorV4';
import { getParsedApiError } from '../api/error';
import { useUiLanguage } from '../contexts/UiLanguageContext';

const REFRESH_MS = 5 * 60 * 1000;
const PROMPT = '通过已连接的 GitHub 读取我当前股票项目 main 中的 '
  + 'INVESTOR_CHATGPT_HANDOFF.md 与 data/investor_chatgpt_handoff/latest.json，'
  + '核查最新交易日、发布时的不可变原始文件和所有来源时效；'
  + '请给出持仓优先的研究摘要、实证支持与反证、正式信号与研究建议的差异、'
  + '独立机会、趋势及现金限制。缺失或过期必须标记，不得猜测现金、成交、'
  + '今天价格或自动交易权限。';

const I18N = {
  zh: {
    title: '投资决策研报',
    subtitle: '程序生成的最新可读取快照；不是交易指令，也不自动运行 ChatGPT。',
    refresh: '刷新数据',
    refreshing: '读取中…',
    stale: '非当前可执行行情',
    fresh: '数据源读取成功',
    remote: '已读取 GitHub main 交接清单',
    local: '仅已部署的历史快照，GitHub 最新数据未证实',
    missing: '尚无可用的 H1 交接产物',
    noOrders: '当前可验证立即买单：0',
    date: '已核验市场数据截至',
    generated: '报告生成于',
    retrieved: '页面读取于',
    first: '我的持仓（已记录历史参考）',
    historical: '以下记录不是今天的可执行指令。可用股数统一为 0。',
    shares: '原记录数量',
    close: '历史参考价格',
    valuation: '价值区间',
    action: '原记录动作',
    unknown: '未验证',
    evidence: '发布时原始报告',
    funds: '基金状态',
    cash: '资金计划',
    planning: '历史计划资金',
    broker: '券商实时现金',
    other: '机会与趋势',
    formal: '可验证新增正式机会：0',
    research: '研究线索（非正式交易权限）',
    empty: '当前没有通过现有全部条件的即时操作',
    source: '数据来源与风险',
    original: '完整来源链接（不可变快照）',
    chat: '需要更深入研究？',
    copy: '复制 ChatGPT 网页版提示词',
    copied: '已复制提示词',
    copyError: '复制失败，请在仓库文档中查看提示词',
    open: '主动打开 ChatGPT',
    error: '获取数据失败',
    execution: '券商持仓、现金、公告与可执行报价缺少独立实时证明；本页只提供历史研究。',
  },
  en: {
    title: 'Investor decision report',
    subtitle: 'A dated program-produced snapshot, not orders or an automatic ChatGPT session.',
    refresh: 'Refresh',
    refreshing: 'Loading…',
    stale: 'Not executable current quotes',
    fresh: 'Source retrieved',
    remote: 'Fetched the GitHub main handoff',
    local: 'Deployed historical copy only; current GitHub main is unverified',
    missing: 'No verified H1 handoff is available',
    noOrders: 'Immediately verified new orders: 0',
    date: 'Last validated market date',
    generated: 'Report generated',
    retrieved: 'Page retrieved',
    first: 'Existing holdings (historical reference)',
    historical: 'These are not instructions for today. Executable quantity remains zero.',
    shares: 'Recorded shares',
    close: 'Frozen reference price',
    valuation: 'Value interval',
    action: 'Recorded action',
    unknown: 'Unverified',
    evidence: 'Original publication-time report',
    funds: 'Fund status',
    cash: 'Capital plan',
    planning: 'Dated planning cash',
    broker: 'Live brokerage cash',
    other: 'Opportunities and trends',
    formal: 'Verified new Formal opportunities: 0',
    research: 'Research leads only (not trading authority)',
    empty: 'No new immediate actions satisfy all existing conditions',
    source: 'Sources and blockers',
    original: 'Exact publication-time source',
    chat: 'Need a deeper analysis?',
    copy: 'Copy on-demand ChatGPT prompt',
    copied: 'Prompt copied',
    copyError: 'Unable to copy. See the repository prompt.',
    open: 'Open ChatGPT manually',
    error: 'Failed to load report',
    execution: 'Live broker positions, cash, original filings and executable quotes have not been independently verified.',
  },
} as const;

function formatNumber(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value);
}

function actionPriority(row: InvestorV4Holding): number {
  const action = row.recorded_formal_action || '';
  if (action.startsWith('EXIT') || action.startsWith('REDUCE')) return 0;
  if (action.startsWith('BUY') || action.startsWith('ADD')) return 1;
  return 2;
}

function immutableSourceUrl(input?: string): string | undefined {
  if (!input) return undefined;
  try {
    const url = new URL(input);
    if (url.protocol !== 'https:' || url.hostname !== 'api.github.com') return undefined;
    if (!/^\/repos\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/git\/blobs\/[a-f0-9]{40}$/.test(url.pathname)) return undefined;
    if (url.username || url.password || url.search || url.hash) return undefined;
    return url.href;
  } catch {
    return undefined;
  }
}

const InvestorV4Page: React.FC = () => {
  const { language } = useUiLanguage();
  const t = I18N[language === 'en' ? 'en' : 'zh'];
  const mounted = useRef(true);
  const [response, setResponse] = useState<InvestorV4DeliveryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<'idle' | 'done' | 'failed'>('idle');

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      const result = await investorV4Api.latest();
      if (!mounted.current) return;
      setResponse(result);
      setError(null);
    } catch (cause) {
      if (!mounted.current) return;
      // Preserve the previously observed dated snapshot, not a fake live update.
      setError(getParsedApiError(cause).message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void reload();
    const id = window.setInterval(() => void reload(), REFRESH_MS);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [reload]);

  useEffect(() => {
    document.title = t.title;
  }, [t.title]);

  const manifest = response?.hand_off;
  const holdings = useMemo(
    () => [...(manifest?.holdings || [])].sort((a, b) => actionPriority(a) - actionPriority(b)),
    [manifest],
  );
  const exactDashboard = immutableSourceUrl(manifest?.source_files?.dashboard?.immutable_blob_url);
  const stale = manifest?.feeds.market_eod.status !== 'UPSTREAM_FRESH_CALENDAR_UNVERIFIED';
  const sourceRemote = response?.delivery === 'GITHUB_MAIN_READ';

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(PROMPT);
      setCopyStatus('done');
    } catch {
      setCopyStatus('failed');
    }
  };

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5 pb-14">
      <header className="rounded-2xl border border-border bg-card p-5 shadow-soft-card">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-foreground">{t.title}</h1>
            <p className="mt-2 max-w-2xl text-sm text-secondary-text">{t.subtitle}</p>
          </div>
          <button
            type="button"
            disabled={loading}
            onClick={() => void reload()}
            className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm text-foreground hover:bg-hover disabled:opacity-60"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            {loading ? t.refreshing : t.refresh}
          </button>
        </div>
        {error && <p role="alert" className="mt-3 text-sm text-red-500">{t.error}: {error}</p>}
        <div className="mt-4 rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-3 text-sm">
          <div className="flex items-center gap-2 font-medium text-foreground">
            <ShieldAlert className="h-4 w-4" aria-hidden="true" />
            {manifest && !stale ? t.fresh : t.stale}
          </div>
          <p className="mt-1 text-secondary-text">{t.execution}</p>
        </div>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><p className="text-secondary-text">{t.date}</p>
            <p className="font-semibold text-foreground">{manifest?.market_session_as_of ?? '—'}</p>
          </div>
          <div><p className="text-secondary-text">{t.generated}</p>
            <p className="text-foreground">{manifest?.generated_at ?? '—'}</p>
          </div>
          <div><p className="text-secondary-text">{t.retrieved}</p>
            <p className="text-foreground">{response?.retrieved_at ?? '—'}</p>
          </div>
          <div><p className="text-secondary-text">{t.noOrders}</p>
            <p className="font-semibold text-foreground">0</p>
          </div>
        </div>
        <p className="mt-4 text-xs text-secondary-text">
          {sourceRemote ? t.remote : t.local}
          {response?.warnings?.length ? ' · ' + response.warnings.join(', ') : ''}
        </p>
      </header>

      {!manifest ? (
        <section className="rounded-2xl border border-border bg-card p-8 text-center text-secondary-text">
          {t.missing}
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-xl font-semibold text-foreground">{t.first}</h2>
            <p className="mt-1 text-sm text-secondary-text">{t.historical}</p>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {holdings.map((h) => (
                <article key={h.code} className="rounded-xl border border-border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-semibold text-foreground">{h.name} <span className="text-xs text-secondary-text">{h.code}</span></h3>
                    <span className="rounded-lg bg-amber-400/10 px-3 py-1 text-xs text-foreground">
                      {t.action}: {h.recorded_formal_action || t.unknown}
                    </span>
                  </div>
                  <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                    <div><dt className="text-secondary-text">{t.shares}</dt>
                      <dd className="text-foreground">{formatNumber(h.last_reported_quantity)}</dd></div>
                    <div><dt className="text-secondary-text">{t.close} · {h.reference_as_of || '—'}</dt>
                      <dd className="text-foreground">{formatNumber(h.frozen_reference_price)}</dd></div>
                    <div className="col-span-2"><dt className="text-secondary-text">{t.valuation}</dt>
                      <dd className="text-foreground">{formatNumber(h.value_range?.[0])} – {formatNumber(h.value_range?.[1])}
                        <span className="ml-2 text-xs text-secondary-text">{h.valuation_confidence || t.unknown}</span>
                      </dd></div>
                  </dl>
                  {exactDashboard && (
                    <a href={exactDashboard} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm text-foreground underline">
                      {t.evidence} <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
                    </a>
                  )}
                </article>
              ))}
            </div>
            {!holdings.length && <p className="mt-4 text-sm text-secondary-text">{t.empty}</p>}
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <article className="rounded-2xl border border-border bg-card p-5">
              <h2 className="text-lg font-semibold text-foreground">{t.funds} · {t.cash}</h2>
              <p className="mt-3 text-sm text-secondary-text">
                {t.funds}: <span className="text-foreground">{manifest.feeds.funds?.status || t.unknown}</span>
              </p>
              <p className="mt-2 text-sm text-secondary-text">
                {t.planning}: <span className="text-foreground">{formatNumber(manifest.feeds.planning_cash?.amount_cny)}</span>
                {' · '}{manifest.feeds.planning_cash?.as_of || t.unknown}
              </p>
              <p className="mt-2 text-sm text-secondary-text">{t.broker}: {t.unknown}</p>
            </article>
            <article className="rounded-2xl border border-border bg-card p-5">
              <h2 className="text-lg font-semibold text-foreground">{t.other}</h2>
              <p className="mt-3 text-sm font-medium text-foreground">{t.formal}</p>
              <p className="mt-2 text-sm text-secondary-text">
                {t.research}: {formatNumber(manifest.research_audit?.research_buy_count)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                {(manifest.trend_research || []).map((trend) => (
                  <span key={trend.trend_id} className="rounded-lg border border-border px-2 py-1 text-xs text-secondary-text">
                    {trend.trend_id} · {trend.authority}
                  </span>
                ))}
              </div>
            </article>
          </section>

          <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-lg font-semibold text-foreground">{t.source}</h2>
            <p className="mt-2 break-all text-sm text-secondary-text">
              {(manifest.blocking_reasons || []).join(' · ')}
            </p>
            {exactDashboard && (
              <a href={exactDashboard} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-sm text-foreground underline">
                {t.original} <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </a>
            )}
          </section>
        </>
      )}

      <section className="rounded-2xl border border-border bg-card p-5">
        <h2 className="text-lg font-semibold text-foreground">{t.chat}</h2>
        <p className="mt-1 text-sm text-secondary-text">{t.subtitle}</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="button" onClick={() => void copyPrompt()} className="inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm text-foreground hover:bg-hover">
            <ClipboardCopy className="h-4 w-4" aria-hidden="true" /> {t.copy}
          </button>
          <a href="https://chatgpt.com/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-xl border border-border px-4 py-2 text-sm text-foreground hover:bg-hover">
            {t.open} <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
        {copyStatus !== 'idle' && <p role="status" className="mt-2 text-sm text-secondary-text">{copyStatus === 'done' ? t.copied : t.copyError}</p>}
      </section>
    </div>
  );
};

export default InvestorV4Page;
