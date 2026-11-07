import { useText } from '../i18n';
import { memo, useState } from 'react';
import { Handle, Position } from '@xyflow/react';
import type { HandleDefinition } from '../config/nodeRegistry';

interface CustomNodeData {
    label: string;
    nodeType: string;
    io?: {
        inputs: HandleDefinition[];
        outputs: HandleDefinition[];
    };
    params?: Record<string, unknown>;
}

const nodeLabels: Record<string, [string, string]> = {
    'data.fetch_stock': ['Stock prices', '股票行情'],
    'data.fetch_crypto': ['Crypto prices', '加密资产行情'],
    'indicator.ma': ['Moving average', '移动平均线'],
    'indicator.crossover': ['Crossover', '交叉检测'],
    'indicator.rsi': ['RSI', '相对强弱指标'],
    'indicator.macd': ['MACD', 'MACD'],
    'logic.condition': ['Trade condition', '交易条件'],
    'signal.buy': ['Buy signal', '买入信号'],
    'signal.sell': ['Sell signal', '卖出信号'],
    'signal.hold': ['Hold signal', '观望信号'],
};

function CustomNode({ data, selected }: { data: CustomNodeData; selected?: boolean }) {
    const t = useText();
    const [hoveredHandle, setHoveredHandle] = useState<string | null>(null);

    const inputs = data.io?.inputs || [];
    const outputs = data.io?.outputs || [];
    const summary = ['symbol', 'timeframe', 'limit', 'period', 'ma_type', 'condition', 'condition_expr']
        .map(key => data.params?.[key])
        .filter(value => typeof value === 'number' || typeof value === 'string')
        .join(' · ');
    const headerHeight = summary ? 68 : 50;
    const maxHandles = Math.max(inputs.length, outputs.length, 1);
    const nodeHeight = Math.max(80, maxHandles * 24 + headerHeight);

    // Ensure nodeType has a fallback value to prevent crashes
    const nodeType = data.nodeType || 'custom.node';
    const localized = nodeLabels[nodeType];
    const label = localized && (!data.label || data.label === nodeType) ? t(...localized) : data.label || t('Node', '节点');

    const getNodeColor = (type: string) => {
        const lowerType = type.toLowerCase();
        if (lowerType.includes('data') || lowerType.includes('fetch')) return '#287b75';  // Sky
        if (lowerType.includes('indicator') || lowerType.includes('ma') || lowerType.includes('rsi')) return '#3a8154';  // Indigo
        if (lowerType.includes('condition') || lowerType.includes('logic') || lowerType.includes('if')) return '#9a681d';  // Amber
        if (lowerType.includes('signal') || lowerType.includes('buy') || lowerType.includes('sell')) return '#8263a2';  // Purple
        if (lowerType.includes('backtest') || lowerType.includes('execution') || lowerType.includes('run')) return '#725995';  // Violet
        if (lowerType.includes('agent') || lowerType.includes('llm')) return '#a45473';  // Pink
        if (lowerType.includes('tool') || lowerType.includes('util')) return '#65796d';  // Slate
        return '#3a8154';  // Default indigo
    };

    const borderColor = getNodeColor(nodeType);

    return (
        <div
            className={`relative rounded-xl border-2 transition-all ${selected ? 'shadow-lg' : 'shadow-md'
                }`}
            style={{
                background: 'var(--color-surface)',
                borderColor,
                minWidth: 160,
                height: nodeHeight,
                boxShadow: selected ? `0 0 20px ${borderColor}40` : undefined,
            }}
        >
            {/* Header */}
            <div
                className="px-3 py-2 text-center border-b"
                style={{ borderColor: borderColor + '40' }}
            >
                <div className="text-[10px] text-muted uppercase tracking-wider">
                    {nodeType.split('.')[0]}
                </div>
                <div className="text-sm font-semibold text-ink truncate">
                    {label}
                </div>
                {summary && <div className="max-w-52 truncate text-xs text-body" title={summary}>{summary}</div>}
            </div>

            {/* Input Handles (Left) */}
            {inputs.map((input, index) => {
                const top = headerHeight + ((index + 0.5) / inputs.length) * (nodeHeight - headerHeight);
                const handleId = `input_${input.name}`;
                return (
                    <div key={handleId}>
                        <Handle
                            type="target"
                            position={Position.Left}
                            id={handleId}
                            style={{ top, background: borderColor }}
                            className="!w-3 !h-3 !border-2 !border-surface"
                            onMouseEnter={() => setHoveredHandle(handleId)}
                            onMouseLeave={() => setHoveredHandle(null)}
                        />
                        {/* Handle Label */}
                        <div
                            className="absolute text-[10px] text-muted pointer-events-none"
                            style={{ left: 12, top: top - 6 }}
                        >
                            {input.name}
                        </div>
                        {/* Tooltip */}
                        {hoveredHandle === handleId && (
                            <div
                                className="absolute z-50 px-4 py-3 text-sm bg-surface border border-line-strong rounded-lg shadow-xl min-w-[180px]"
                                style={{ left: -200, top: top - 20 }}
                            >
                                <div className="font-semibold text-ink text-base">{input.name}</div>
                                <div className="text-body mt-1">{input.description}</div>
                                <div className="text-muted text-xs mt-2 pt-2 border-t border-line">{t('Type', '类型')} · {input.type}</div>
                            </div>
                        )}
                    </div>
                );
            })}

            {/* Output Handles (Right) */}
            {outputs.map((output, index) => {
                const top = headerHeight + ((index + 0.5) / outputs.length) * (nodeHeight - headerHeight);
                const handleId = `output_${output.name}`;
                return (
                    <div key={handleId}>
                        <Handle
                            type="source"
                            position={Position.Right}
                            id={handleId}
                            style={{ top, background: borderColor }}
                            className="!w-3 !h-3 !border-2 !border-surface"
                            onMouseEnter={() => setHoveredHandle(handleId)}
                            onMouseLeave={() => setHoveredHandle(null)}
                        />
                        {/* Handle Label */}
                        <div
                            className="absolute text-[10px] text-muted pointer-events-none text-right"
                            style={{ right: 12, top: top - 6 }}
                        >
                            {output.name}
                        </div>
                        {/* Tooltip */}
                        {hoveredHandle === handleId && (
                            <div
                                className="absolute z-50 px-4 py-3 text-sm bg-surface border border-line-strong rounded-lg shadow-xl min-w-[180px]"
                                style={{ right: -200, top: top - 20 }}
                            >
                                <div className="font-semibold text-ink text-base">{output.name}</div>
                                <div className="text-body mt-1">{output.description}</div>
                                <div className="text-muted text-xs mt-2 pt-2 border-t border-line">{t('Type', '类型')} · {output.type}</div>
                            </div>
                        )}
                    </div>
                );
            })}

            {/* Fallback handles if no I/O defined */}
            {inputs.length === 0 && outputs.length === 0 && (
                <>
                    <Handle
                        type="target"
                        position={Position.Left}
                        className="!bg-line-strong !w-3 !h-3"
                        style={{ top: '50%' }}
                    />
                    <Handle
                        type="source"
                        position={Position.Right}
                        className="!bg-line-strong !w-3 !h-3"
                        style={{ top: '50%' }}
                    />
                </>
            )}
        </div>
    );
}

export default memo(CustomNode);
