import { useText } from '../i18n';
import { useEffect, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, BarChart3, RefreshCw } from 'lucide-react';

const universe = [
    { symbol: 'AAPL', name: 'Apple', nameZh: '苹果' },
    { symbol: 'MSFT', name: 'Microsoft', nameZh: '微软' },
    { symbol: 'NVDA', name: 'NVIDIA', nameZh: '英伟达' },
    { symbol: 'AMZN', name: 'Amazon', nameZh: '亚马逊' },
    { symbol: 'GOOGL', name: 'Alphabet', nameZh: 'Alphabet' },
    { symbol: 'META', name: 'Meta', nameZh: 'Meta' },
];

const periods = [1, 5, 20] as const;
type Period = (typeof periods)[number];

interface Candle {
    timestamp: number;
    close: number;
}

interface History {
    bars: Map<string, number>;
    stale: boolean;
}

const sessionDate = new Intl.DateTimeFormat('sv-SE');

async function loadHistory(symbol: string, signal: AbortSignal): Promise<History> {
    const query = new URLSearchParams({ type: 'stock', market: 'us', timeframe: '1d', limit: '21', symbol });
    const response = await fetch(`/api/v1/data/kline?${query}`, { signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const payload: { data: Candle[]; stale?: boolean } = await response.json();
    const bars = new Map(
        payload.data
            .filter(bar => Number.isFinite(bar.timestamp) && Number.isFinite(bar.close) && bar.close > 0)
            .sort((left, right) => left.timestamp - right.timestamp)
            .map(bar => [sessionDate.format(bar.timestamp), bar.close]),
    );
    if (bars.size === 0) throw new Error('No price history');
    return { bars, stale: payload.stale === true };
}

function formatReturn(value: number | null) {
    return value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function returnColor(value: number | null) {
    if (value == null || value === 0) return 'text-muted';
    return value > 0 ? 'text-brand-ink' : 'text-rose-700';
}

export default function MarketSnapshot() {
    const t = useText();
    const [period, setPeriod] = useState<Period>(1);
    const [refresh, setRefresh] = useState(0);
    const [histories, setHistories] = useState<(History | null)[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const controller = new AbortController();
        Promise.allSettled(universe.map(stock => loadHistory(stock.symbol, controller.signal))).then(results => {
            if (controller.signal.aborted) return;
            setHistories(results.map(result => result.status === 'fulfilled' ? result.value : null));
            setLoading(false);
        });
        return () => controller.abort();
    }, [refresh]);

    const tradingDates = Array.from(new Set(histories.flatMap(history => [...(history?.bars.keys() ?? [])]))).sort();
    const latestDate = tradingDates.at(-1);
    const startDate = tradingDates.at(-1 - period);
    const rows = universe.map((stock, index) => {
        const history = histories[index];
        const close = latestDate ? history?.bars.get(latestDate) : undefined;
        const startClose = startDate ? history?.bars.get(startDate) : undefined;
        return {
            ...stock,
            close,
            change: close !== undefined && startClose !== undefined ? (close / startClose - 1) * 100 : null,
            status: !history ? t('No data', '暂无数据') : close === undefined || startClose === undefined ? t('Missing prices', '区间缺数') : history.stale ? t('Cached prices', '缓存回退') : '',
        };
    });
    const ranked = rows.flatMap(row => row.change == null ? [] : [{ ...row, change: row.change }])
        .sort((left, right) => right.change - left.change);
    const tableRows = [...ranked, ...rows.filter(row => row.change == null)];
    const scale = Math.max(0.1, ...ranked.map(row => Math.abs(row.change)));
    const rises = ranked.filter(row => row.change > 0).length;
    const falls = ranked.filter(row => row.change < 0).length;
    const mean = ranked.length ? ranked.reduce((sum, row) => sum + row.change, 0) / ranked.length : null;

    const reload = () => {
        setLoading(true);
        setRefresh(value => value + 1);
    };

    return (
        <main className="min-w-0 flex-1 overflow-y-auto bg-page" aria-labelledby="market-title">
            <div className="mx-auto max-w-7xl space-y-6 p-5 md:p-8">
                <section className="rounded-3xl border border-line bg-brand-soft p-5 md:p-7">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                            <div className="flex items-center gap-2 text-xs font-semibold text-brand-ink">
                                <BarChart3 size={15} /> {t('U.S. market · Daily prices', '市场观察 · 美股日线')}
                            </div>
                            <h2 id="market-title" className="mt-2 text-3xl font-semibold tracking-tight text-ink">{t('Market snapshot', '行情截面')}</h2>
                            <p className="mt-2 text-sm text-body">{t('Compare closing-price moves for six large technology stocks over the same period.', '比较六只大型科技股在同一交易区间的收盘价变化。')}</p>
                        </div>
                        <button type="button" onClick={reload} disabled={loading}
                            className="flex items-center gap-2 rounded-xl border border-line-strong bg-surface px-4 py-2 text-sm font-medium text-brand-ink hover:bg-subtle disabled:text-muted">
                            <RefreshCw size={15} className={loading ? 'animate-spin' : undefined} /> {t('Reload', '重新载入')}
                        </button>
                    </div>
                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                        <div role="group" aria-label={t('Comparison window', '收益比较区间')} className="flex gap-1 rounded-xl bg-surface p-1">
                            {periods.map(days => (
                                <button key={days} type="button" aria-pressed={days === period} onClick={() => setPeriod(days)}
                                    className={`rounded-lg px-4 py-2 text-sm font-medium ${days === period ? 'bg-brand text-white' : 'text-muted hover:bg-subtle'}`}>
                                    {t(`${days} ${days === 1 ? 'day' : 'days'}`, `${days} 日`)}
                                </button>
                            ))}
                        </div>
                        <p className="text-sm tabular-nums text-body" role="status">
                            {loading ? t('Loading daily prices…', '正在加载日线行情…') : startDate && latestDate ? `${startDate} ${t('to', '至')} ${latestDate}` : t('No dates to compare yet', '暂时没有可比较的日期')}
                        </p>
                    </div>
                </section>

                {!loading && (
                    <>
                        <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
                            {[
                                { label: t('Up', '上涨'), value: t(String(rises), `${rises} 只`), color: 'text-brand-ink' },
                                { label: t('Down', '下跌'), value: t(String(falls), `${falls} 只`), color: 'text-rose-700' },
                                { label: t('Average change', '等权平均涨跌'), value: formatReturn(mean), color: returnColor(mean) },
                                { label: t('Stocks covered', '覆盖标的'), value: `${ranked.length} / ${universe.length}`, color: 'text-ink' },
                            ].map(item => (
                                <div key={item.label} className="rounded-2xl border border-line bg-surface p-4">
                                    <dt className="text-sm text-muted">{item.label}</dt>
                                    <dd className={`mt-1 text-2xl font-semibold tabular-nums ${item.color}`}>{item.value}</dd>
                                </div>
                            ))}
                        </dl>

                        <div className="grid gap-4 lg:grid-cols-2">
                            <section className="min-w-0 rounded-2xl border border-line bg-surface p-5">
                                <h3 className="font-semibold text-ink">{t('Price movers', '涨跌幅排行')}</h3>
                                <p className="mt-1 text-xs text-muted">{t('Sorted by return. Longer bars mean bigger moves.', '按涨跌幅降序，条长表示变动幅度。')}</p>
                                {ranked.length === 0 && <p className="mt-5 text-sm text-muted">{t('There are not enough prices for this period. Try reloading.', '暂无足够的同区间行情，可重新载入。')}</p>}
                                <ol className="mt-5 space-y-3">
                                    {ranked.map(row => (
                                        <li key={row.symbol} className="grid grid-cols-[4rem_minmax(0,1fr)_5rem] items-center gap-3 text-sm">
                                            <span className="font-medium text-ink">{row.symbol}</span>
                                            <div aria-hidden="true" className="h-2.5 rounded-full bg-subtle">
                                                <div className={`h-full rounded-full ${row.change < 0 ? 'bg-rose-400' : 'bg-brand'}`} style={{ width: `${Math.abs(row.change) / scale * 100}%` }} />
                                            </div>
                                            <span className={`flex items-center justify-end gap-1 tabular-nums ${returnColor(row.change)}`}>
                                                {row.change < 0 && <ArrowDownRight size={13} aria-hidden="true" />}
                                                {row.change > 0 && <ArrowUpRight size={13} aria-hidden="true" />}
                                                {formatReturn(row.change)}
                                            </span>
                                        </li>
                                    ))}
                                </ol>
                            </section>

                            <section className="min-w-0 rounded-2xl border border-line bg-surface p-5">
                                <h3 className="font-semibold text-ink">{t('Stock details', '标的明细')}</h3>
                                <div className="mt-3 overflow-x-auto">
                                    <table className="w-full whitespace-nowrap text-left text-sm tabular-nums">
                                        <thead className="border-b border-line text-xs text-muted">
                                            <tr>
                                                <th scope="col" className="py-2 font-medium">{t('Stock', '标的')}</th>
                                                <th scope="col" className="py-2 text-right font-medium">{t('Close (USD)', '收盘价 (USD)')}</th>
                                                <th scope="col" className="py-2 text-right font-medium">{t(`${period}-day change`, `${period} 日涨跌`)}</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {tableRows.map(row => (
                                                <tr key={row.symbol} className="border-b border-line last:border-0">
                                                    <th scope="row" className="py-2 font-medium text-ink">
                                                        {row.symbol} <span className="ml-1 font-normal text-muted">{t(row.name, row.nameZh)}</span>
                                                        {row.status && <span className="ml-2 text-xs font-normal text-muted">{row.status}</span>}
                                                    </th>
                                                    <td className="py-2 text-right text-body">{row.close?.toFixed(2) ?? '—'}</td>
                                                    <td className={`py-2 text-right font-medium ${returnColor(row.change)}`}>{formatReturn(row.change)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>
                        </div>

                        <p className="text-xs leading-relaxed text-muted">
                            {t('Prices come from the Golden Touch daily price API. Dates use your browser’s time zone. Changes use matching start and end closes, and stocks with missing prices are left out of the summary.', '数据来自 Golden Touch 的日线行情接口。日期按浏览器本地日期显示。区间涨跌按相同起止日期的收盘价计算，缺数标的从汇总中排除。样本为上方六只股票。')}
                        </p>
                    </>
                )}
            </div>
        </main>
    );
}
