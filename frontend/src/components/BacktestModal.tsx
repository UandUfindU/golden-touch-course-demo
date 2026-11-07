import { useText } from '../i18n';
import { useEffect, useRef } from 'react';
import { Activity, Loader2, X } from 'lucide-react';

interface EquityPoint {
    timestamp: number;
    equity: number;
}

interface Trade {
    entry_time: number;
    exit_time?: number | null;
    direction: string;
    entry_price: number;
    exit_price?: number | null;
    quantity: number;
    pnl?: number | null;
}

export interface BacktestResult {
    run_id: string;
    symbol?: string;
    timeframe?: string;
    initial_capital?: number;
    commission_rate?: number;
    bars_processed?: number;
    start_time?: number;
    end_time?: number;
    metrics: {
        total_return?: number;
        sharpe_ratio?: number;
        max_drawdown?: number;
        win_rate?: number;
        total_trades?: number;
        winning_trades?: number;
        losing_trades?: number;
        avg_win?: number;
        avg_loss?: number;
    };
    equity_curve?: EquityPoint[];
    trades?: Trade[];
}

interface BacktestModalProps {
    isOpen: boolean;
    onClose: () => void;
    result: BacktestResult | null;
    isLoading: boolean;
    status: string;
    error?: string;
}

function formatNumber(value: number | null | undefined, suffix = '') {
    return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}${suffix}` : '—';
}

function formatDate(timestamp?: number | null) {
    return timestamp == null ? '—' : new Date(timestamp).toLocaleDateString('sv-SE');
}

export default function BacktestModal({ isOpen, onClose, result, isLoading, status, error }: BacktestModalProps) {
    const t = useText();
    const dialog = useRef<HTMLDialogElement>(null);

    useEffect(() => {
        const element = dialog.current;
        if (isOpen && element && !element.open) element.showModal();
    }, [isOpen]);

    if (!isOpen) return null;

    const metrics = result?.metrics;
    const points = result?.equity_curve ?? [];
    const trades = result?.trades ?? [];
    const recentTrades = trades.slice(-10).reverse();

    return (
        <dialog
            ref={dialog}
            aria-labelledby="backtest-heading"
            onCancel={event => { event.preventDefault(); onClose(); }}
            className="fixed inset-0 m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-5xl overflow-y-auto rounded-2xl border border-line bg-surface text-ink shadow-2xl backdrop:bg-scrim/40 backdrop:backdrop-blur-sm"
        >
            <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-surface px-6 py-4">
                <div className="flex items-center gap-3">
                    <Activity className="rounded-lg bg-brand-soft p-2 text-brand-ink" size={38} />
                    <div>
                        <h2 id="backtest-heading" className="text-xl font-bold text-ink">{t('Backtest report', '历史回测报告')}</h2>
                        <p className="mt-0.5 text-xs text-muted">{t('Run settings, equity, and simulated trades', '运行条件、权益走势与模拟成交')}</p>
                    </div>
                </div>
                <button onClick={onClose} className="rounded-lg p-2 hover:bg-hover" aria-label={t('Close backtest report', '关闭回测报告')}>
                    <X size={20} />
                </button>
            </div>

            <div className="space-y-5 p-6">
                {isLoading && (
                    <div role="status" className="flex items-center justify-center gap-3 py-16 text-brand-ink">
                        <Loader2 className="animate-spin" size={24} />
                        {status === '正在获取历史行情' ? t('Fetching price history…', '正在获取历史行情…') : t('Running the backtest…', '正在运行回测…')}
                    </div>
                )}
                {error && (
                    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-red-800">
                        <p className="font-semibold">{t('Backtest failed', '回测失败')}</p>
                        <p className="mt-2 break-words text-sm">{error}</p>
                    </div>
                )}
                {result && metrics && !isLoading && (
                    <>
                        <dl className="flex flex-wrap gap-x-6 gap-y-2 rounded-xl border border-line bg-subtle px-4 py-3 text-sm">
                            <Condition label={t('Symbol / interval', '标的 / 频率')} value={`${result.symbol ?? '—'} / ${result.timeframe ?? '—'}`} />
                            <Condition label={t('Date range', '历史区间')} value={`${formatDate(result.start_time ?? points[0]?.timestamp)} ${t('to', '至')} ${formatDate(result.end_time ?? points.at(-1)?.timestamp)}`} />
                            <Condition label={t('Starting capital', '初始资金')} value={formatNumber(result.initial_capital)} />
                            <Condition label={t('Fee', '费率')} value={formatNumber(result.commission_rate == null ? undefined : result.commission_rate * 100, '%')} />
                            <Condition label={t('Bars', '行情根数')} value={String(result.bars_processed ?? points.length)} />
                        </dl>
                        <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
                            <Metric label={t('Total return', '总收益率')} value={formatNumber(metrics.total_return, '%')} />
                            <Metric label={t('Max drawdown', '最大回撤')} value={formatNumber(metrics.max_drawdown, '%')} />
                            <Metric label={t('Sharpe ratio', '夏普比率')} value={formatNumber(metrics.sharpe_ratio)} />
                            <Metric label={t('Win rate', '胜率')} value={formatNumber(metrics.win_rate, '%')} />
                            <Metric label={t('Closed trades', '已平仓交易')} value={String(metrics.total_trades ?? '—')} />
                        </dl>
                        <section className="rounded-xl border border-line bg-subtle p-4">
                            <h3 className="font-semibold text-ink">{t('Equity curve', '权益走势')}</h3>
                            <EquityChart points={points} />
                        </section>
                        <section className="rounded-xl border border-line bg-subtle p-4">
                            <h3 className="font-semibold text-ink">{t('Recent trades', '最近交易')}</h3>
                            <p className="mt-1 text-xs text-muted">
                                {t('Winners', '盈利')} {metrics.winning_trades ?? '—'} / {t('Loss or break-even', '亏损或持平')} {metrics.losing_trades ?? '—'}
                                <span className="ml-4">{t('Avg. win', '平均盈利')} {formatNumber(metrics.avg_win)} / {t('Avg. loss', '平均亏损')} {formatNumber(metrics.avg_loss)}</span>
                            </p>
                            {recentTrades.length === 0 ? <p className="mt-3 text-sm text-muted">{t('No trades in this period', '该区间内暂无交易')}</p> : (
                                <div className="mt-3 overflow-x-auto">
                                    <table className="w-full whitespace-nowrap text-left text-sm tabular-nums">
                                        <thead className="border-b border-line text-xs text-muted">
                                            <tr>
                                                {[t('Opened', '开仓'), t('Closed', '平仓'), t('Side', '方向'), t('Entry price', '开仓价'), t('Exit price', '平仓价'), t('Quantity', '数量'), t('P&L', '盈亏')].map(label => (
                                                    <th scope="col" key={label} className="px-2 py-2 font-medium">{label}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {recentTrades.map((trade, index) => (
                                                <tr key={`${trade.entry_time}-${index}`} className="border-b border-line">
                                                    <td className="px-2 py-2">{formatDate(trade.entry_time)}</td>
                                                    <td className="px-2 py-2">{formatDate(trade.exit_time)}</td>
                                                    <td className="px-2 py-2">{trade.direction === 'long' ? t('Long', '多头') : trade.direction === 'short' ? t('Short', '空头') : trade.direction}</td>
                                                    <td className="px-2 py-2">{formatNumber(trade.entry_price)}</td>
                                                    <td className="px-2 py-2">{formatNumber(trade.exit_price)}</td>
                                                    <td className="px-2 py-2">{formatNumber(trade.quantity)}</td>
                                                    <td className={`px-2 py-2 ${(trade.pnl ?? 0) < 0 ? 'text-rose-700' : 'text-ink'}`}>
                                                        {formatNumber(trade.exit_time == null ? undefined : trade.pnl)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </section>
                    </>
                )}
            </div>
        </dialog>
    );
}

function Condition({ label, value }: { label: string; value: string }) {
    return <div><dt className="text-xs text-muted">{label}</dt><dd className="mt-1 tabular-nums text-ink">{value}</dd></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl border border-line bg-brand-soft px-4 py-3">
            <dt className="text-xs text-brand-ink">{label}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums text-ink">{value}</dd>
        </div>
    );
}

function EquityChart({ points }: { points: EquityPoint[] }) {
    const t = useText();
    const values = points.map(point => point.equity).filter(Number.isFinite);
    if (values.length === 0) return <p className="py-8 text-center text-sm text-muted">{t('No equity data yet', '暂无权益数据')}</p>;

    const max = Math.max(...values);
    const min = Math.min(...values);
    const width = 800;
    const height = 150;
    const line = values.map((value, index) => {
        const x = values.length === 1 ? width / 2 : index * width / (values.length - 1);
        const y = max === min ? height / 2 : 4 + (max - value) / (max - min) * (height - 8);
        return `${x},${y}`;
    }).join(' ');

    return (
        <>
            <div className="mt-3 flex gap-3">
                <div className="flex flex-col justify-between py-1 text-right text-xs tabular-nums text-muted">
                    <span>{formatNumber(max)}</span><span>{formatNumber(min)}</span>
                </div>
                <svg role="img" aria-label={t('Historical equity curve', '历史权益曲线')} className="h-32 min-w-0 flex-1 md:h-40" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
                    {[4, 75, 146].map(y => <line key={y} x1="0" x2={width} y1={y} y2={y} className="stroke-line-strong" />)}
                    {values.length === 1 ? <circle cx={width / 2} cy={height / 2} r="4" className="fill-brand" /> :
                        <polyline points={line} fill="none" strokeWidth="2" vectorEffect="non-scaling-stroke" className="stroke-brand" />}
                </svg>
            </div>
            <div className="mt-1 flex justify-between pl-14 text-xs text-muted">
                <span>{formatDate(points[0]?.timestamp)}</span><span>{formatDate(points.at(-1)?.timestamp)}</span>
            </div>
        </>
    );
}
