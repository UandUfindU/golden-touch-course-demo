// Node Registry with I/O Schemas
// Industrial-grade node definitions for the visual editor

export interface HandleDefinition {
    name: string;
    type: 'number' | 'boolean' | 'series' | 'signal' | 'any';
    description: string;
}

export interface NodeIOSchema {
    inputs: HandleDefinition[];
    outputs: HandleDefinition[];
}

export interface NodeDefinition {
    type: string;
    label: string;
    category: string;
    color: string;
    io: NodeIOSchema;
}

export const nodeRegistry: Record<string, NodeDefinition> = {
    // ===== Data Input =====
    'input.stock_data': {
        type: 'input.stock_data',
        label: '股票数据源',
        category: '数据输入',
        color: '#06b6d4',
        io: {
            inputs: [],
            outputs: [
                { name: 'open', type: 'series', description: '开盘价序列' },
                { name: 'high', type: 'series', description: '最高价序列' },
                { name: 'low', type: 'series', description: '最低价序列' },
                { name: 'close', type: 'series', description: '收盘价序列' },
                { name: 'volume', type: 'series', description: '成交量序列' },
            ],
        },
    },
    'input.crypto_data': {
        type: 'input.crypto_data',
        label: '加密货币数据',
        category: '数据输入',
        color: '#06b6d4',
        io: {
            inputs: [],
            outputs: [
                { name: 'open', type: 'series', description: '开盘价' },
                { name: 'high', type: 'series', description: '最高价' },
                { name: 'low', type: 'series', description: '最低价' },
                { name: 'close', type: 'series', description: '收盘价' },
                { name: 'volume', type: 'series', description: '成交量' },
            ],
        },
    },

    // ===== Technical Indicators =====
    'indicator.ma': {
        type: 'indicator.ma',
        label: 'MA 移动平均',
        category: '技术指标',
        color: '#3b82f6',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列 (如 close)' },
            ],
            outputs: [
                { name: 'value', type: 'series', description: 'MA 值序列' },
            ],
        },
    },
    'indicator.ema': {
        type: 'indicator.ema',
        label: 'EMA 指数平均',
        category: '技术指标',
        color: '#3b82f6',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列' },
            ],
            outputs: [
                { name: 'value', type: 'series', description: 'EMA 值序列' },
            ],
        },
    },
    'indicator.rsi': {
        type: 'indicator.rsi',
        label: 'RSI 相对强弱',
        category: '技术指标',
        color: '#3b82f6',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列' },
            ],
            outputs: [
                { name: 'value', type: 'series', description: 'RSI 值 (0-100)' },
            ],
        },
    },
    'indicator.macd': {
        type: 'indicator.macd',
        label: 'MACD',
        category: '技术指标',
        color: '#3b82f6',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列' },
            ],
            outputs: [
                { name: 'macd', type: 'series', description: 'MACD 线' },
                { name: 'signal', type: 'series', description: '信号线' },
                { name: 'histogram', type: 'series', description: '柱状图' },
            ],
        },
    },
    'indicator.bollinger': {
        type: 'indicator.bollinger',
        label: '布林带',
        category: '技术指标',
        color: '#3b82f6',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列' },
            ],
            outputs: [
                { name: 'upper', type: 'series', description: '上轨' },
                { name: 'middle', type: 'series', description: '中轨' },
                { name: 'lower', type: 'series', description: '下轨' },
            ],
        },
    },

    // ===== Logic Conditions =====
    'condition.crossover': {
        type: 'condition.crossover',
        label: '金叉/死叉',
        category: '逻辑条件',
        color: '#f59e0b',
        io: {
            inputs: [
                { name: 'fast', type: 'series', description: '快线' },
                { name: 'slow', type: 'series', description: '慢线' },
            ],
            outputs: [
                { name: 'crossover', type: 'boolean', description: '金叉信号' },
                { name: 'crossunder', type: 'boolean', description: '死叉信号' },
            ],
        },
    },
    'condition.compare': {
        type: 'condition.compare',
        label: '比较运算',
        category: '逻辑条件',
        color: '#f59e0b',
        io: {
            inputs: [
                { name: 'left', type: 'any', description: '左操作数' },
                { name: 'right', type: 'any', description: '右操作数' },
            ],
            outputs: [
                { name: 'result', type: 'boolean', description: '比较结果' },
            ],
        },
    },
    'condition.threshold': {
        type: 'condition.threshold',
        label: '阈值判断',
        category: '逻辑条件',
        color: '#f59e0b',
        io: {
            inputs: [
                { name: 'value', type: 'number', description: '输入值' },
            ],
            outputs: [
                { name: 'above', type: 'boolean', description: '高于阈值' },
                { name: 'below', type: 'boolean', description: '低于阈值' },
            ],
        },
    },
    'condition.and': {
        type: 'condition.and',
        label: '与 (AND)',
        category: '逻辑条件',
        color: '#f59e0b',
        io: {
            inputs: [
                { name: 'a', type: 'boolean', description: '条件 A' },
                { name: 'b', type: 'boolean', description: '条件 B' },
            ],
            outputs: [
                { name: 'result', type: 'boolean', description: 'A AND B' },
            ],
        },
    },
    'condition.or': {
        type: 'condition.or',
        label: '或 (OR)',
        category: '逻辑条件',
        color: '#f59e0b',
        io: {
            inputs: [
                { name: 'a', type: 'boolean', description: '条件 A' },
                { name: 'b', type: 'boolean', description: '条件 B' },
            ],
            outputs: [
                { name: 'result', type: 'boolean', description: 'A OR B' },
            ],
        },
    },

    // ===== Trading Signals =====
    'signal.buy': {
        type: 'signal.buy',
        label: '买入信号',
        category: '交易信号',
        color: '#10b981',
        io: {
            inputs: [
                { name: 'condition', type: 'boolean', description: '触发条件' },
            ],
            outputs: [
                { name: 'signal', type: 'signal', description: '买入信号' },
            ],
        },
    },
    'signal.sell': {
        type: 'signal.sell',
        label: '卖出信号',
        category: '交易信号',
        color: '#10b981',
        io: {
            inputs: [
                { name: 'condition', type: 'boolean', description: '触发条件' },
            ],
            outputs: [
                { name: 'signal', type: 'signal', description: '卖出信号' },
            ],
        },
    },
    'signal.stop_loss': {
        type: 'signal.stop_loss',
        label: '止损信号',
        category: '交易信号',
        color: '#10b981',
        io: {
            inputs: [
                { name: 'price', type: 'series', description: '当前价格' },
                { name: 'threshold', type: 'number', description: '止损阈值' },
            ],
            outputs: [
                { name: 'signal', type: 'signal', description: '止损信号' },
            ],
        },
    },

    // ===== Execution / Backtest =====
    'execution.backtest': {
        type: 'execution.backtest',
        label: '回测引擎',
        category: '执行/回测',
        color: '#8b5cf6',
        io: {
            inputs: [
                { name: 'data', type: 'series', description: '市场数据' },
                { name: 'buy_signal', type: 'signal', description: '买入信号' },
                { name: 'sell_signal', type: 'signal', description: '卖出信号' },
            ],
            outputs: [
                { name: 'equity', type: 'series', description: '权益曲线' },
                { name: 'trades', type: 'any', description: '交易记录' },
                { name: 'metrics', type: 'any', description: '绩效指标' },
            ],
        },
    },
    'execution.position_size': {
        type: 'execution.position_size',
        label: '仓位计算',
        category: '执行/回测',
        color: '#8b5cf6',
        io: {
            inputs: [
                { name: 'capital', type: 'number', description: '可用资金' },
                { name: 'risk', type: 'number', description: '风险比例' },
            ],
            outputs: [
                { name: 'size', type: 'number', description: '建议仓位' },
            ],
        },
    },

    // ===== Utility =====
    'utility.math': {
        type: 'utility.math',
        label: '数学运算',
        category: '计算工具',
        color: '#ec4899',
        io: {
            inputs: [
                { name: 'a', type: 'number', description: '操作数 A' },
                { name: 'b', type: 'number', description: '操作数 B' },
            ],
            outputs: [
                { name: 'result', type: 'number', description: '运算结果' },
            ],
        },
    },
    'utility.delay': {
        type: 'utility.delay',
        label: '延迟/移位',
        category: '计算工具',
        color: '#ec4899',
        io: {
            inputs: [
                { name: 'source', type: 'series', description: '输入序列' },
            ],
            outputs: [
                { name: 'shifted', type: 'series', description: '移位后序列' },
            ],
        },
    },
};

// Group nodes by category for the palette
export function getNodesByCategory(): { name: string; color: string; nodes: NodeDefinition[] }[] {
    const categories: Record<string, { color: string; nodes: NodeDefinition[] }> = {};

    Object.values(nodeRegistry).forEach((node) => {
        if (!categories[node.category]) {
            categories[node.category] = { color: node.color, nodes: [] };
        }
        categories[node.category].nodes.push(node);
    });

    return Object.entries(categories).map(([name, data]) => ({
        name,
        color: data.color,
        nodes: data.nodes,
    }));
}
