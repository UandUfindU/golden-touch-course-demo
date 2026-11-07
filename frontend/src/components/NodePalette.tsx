import type { DragEvent } from 'react';
import { Database, TrendingUp, GitBranch, Zap, PlayCircle, Calculator } from 'lucide-react';
import { getNodesByCategory, type NodeDefinition } from '../config/nodeRegistry';

const categoryIcons: Record<string, typeof Database> = {
    '数据输入': Database,
    '技术指标': TrendingUp,
    '逻辑条件': GitBranch,
    '交易信号': Zap,
    '执行/回测': PlayCircle,
    '计算工具': Calculator,
};

export default function NodePalette() {
    const categories = getNodesByCategory();

    const onDragStart = (event: DragEvent, node: NodeDefinition) => {
        const dragData = {
            type: node.type,
            label: node.label,
            io: node.io,
        };
        event.dataTransfer.setData('application/reactflow', JSON.stringify(dragData));
        event.dataTransfer.effectAllowed = 'move';
    };

    return (
        <div className="h-[calc(100%-40px)] px-4 py-2 flex gap-6 overflow-x-auto">
            {categories.map((category) => {
                const Icon = categoryIcons[category.name] || Database;
                return (
                    <div key={category.name} className="flex-shrink-0">
                        <div className="flex items-center gap-1.5 mb-2">
                            <Icon size={14} style={{ color: category.color }} />
                            <span className="text-xs font-medium text-slate-400">{category.name}</span>
                        </div>
                        <div className="flex gap-2 flex-wrap max-w-[220px]">
                            {category.nodes.map((node) => {
                                const inputCount = node.io.inputs.length;
                                const outputCount = node.io.outputs.length;
                                return (
                                    <div
                                        key={node.type}
                                        draggable
                                        onDragStart={(e) => onDragStart(e, node)}
                                        className="group px-2 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 border border-slate-600 rounded-lg text-xs text-slate-300 cursor-grab active:cursor-grabbing transition-colors"
                                        style={{ borderColor: category.color + '40' }}
                                        title={`输入: ${inputCount} | 输出: ${outputCount}`}
                                    >
                                        <div className="flex items-center gap-1">
                                            <span className="text-slate-500">{inputCount}→</span>
                                            <span>{node.label}</span>
                                            <span className="text-slate-500">→{outputCount}</span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
