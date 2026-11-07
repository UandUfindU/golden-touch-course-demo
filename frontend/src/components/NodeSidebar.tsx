import { useText } from '../i18n';
import { useState, useEffect } from 'react';
import type { DragEvent } from 'react';
import { ChevronLeft, Database, TrendingUp, GitBranch, Zap, PlayCircle, Calculator, Bot, Settings, Loader2 } from 'lucide-react';
import { fetchNodes, groupNodesByCategory, type NodeDefinition } from '../services/nodeApi';

interface NodeSidebarProps {
    onCollapse: () => void;
}

// Keep node categories distinct on the light workbench.
const categoryColors: Record<string, string> = {
    'data': '#287b75',
    'indicator': '#3a8154',
    'condition': '#9a681d',
    'logic': '#9a681d',
    'signal': '#8263a2',
    'backtest': '#725995',
    'execution': '#725995',
    'agent': '#a45473',
    'tool': '#65796d',
    'engine': '#725995',
    'structure': '#65796d',
    'workflow': '#806599',
    'core': '#566b60',
};

const categoryIcons: Record<string, typeof Database> = {
    'data': Database,
    'indicator': TrendingUp,
    'condition': GitBranch,
    'logic': GitBranch,
    'signal': Zap,
    'backtest': PlayCircle,
    'execution': PlayCircle,
    'agent': Bot,
    'tool': Settings,
    'engine': PlayCircle,
    'structure': Settings,
    'workflow': Settings,
    'core': Calculator,
};

function getCategoryIcon(category: string): typeof Database {
    const lowerCat = category.toLowerCase();
    for (const [key, icon] of Object.entries(categoryIcons)) {
        if (lowerCat.includes(key)) return icon;
    }
    return Database;
}

function getCategoryColor(category: string): string {
    const lowerCat = category.toLowerCase();
    for (const [key, color] of Object.entries(categoryColors)) {
        if (lowerCat.includes(key)) return color;
    }
    return '#3a8154';
}

export default function NodeSidebar({ onCollapse }: NodeSidebarProps) {
    const t = useText();
    const [categories, setCategories] = useState<{ name: string; color: string; nodes: NodeDefinition[] }[]>([]);
    const [activeCategory, setActiveCategory] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        async function loadNodes() {
            setLoading(true);
            setError(false);
            try {
                const nodes = await fetchNodes();
                // Override colors with our theme
                const nodesWithColors = nodes.map(n => ({
                    ...n,
                    color: getCategoryColor(n.category)
                }));
                const grouped = groupNodesByCategory(nodesWithColors);
                setCategories(grouped);
                if (grouped.length > 0) {
                    setActiveCategory(grouped[0].name);
                }
            } catch (e) {
                setError(true);
                console.error(e);
            } finally {
                setLoading(false);
            }
        }
        loadNodes();
    }, []);

    const activeNodes = categories.find((c) => c.name === activeCategory)?.nodes || [];

    const onDragStart = (event: DragEvent, node: NodeDefinition) => {
        const dragData = {
            type: node.type,
            label: node.name,
            io: node.io,
        };
        event.dataTransfer.setData('application/reactflow', JSON.stringify(dragData));
        event.dataTransfer.effectAllowed = 'move';
    };

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center bg-surface">
                <Loader2 className="animate-spin text-muted" size={24} />
                <span className="text-xs text-muted mt-2">{t('Loading nodes…', '加载节点…')}</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="h-full flex flex-col items-center justify-center bg-surface p-4">
                <span className="text-xs text-red-700">{t('Could not load the node library', '无法加载节点列表')}</span>
                <button
                    onClick={() => window.location.reload()}
                    className="mt-2 text-xs text-brand-ink hover:underline"
                >
                    {t('Try again', '重试')}
                </button>
            </div>
        );
    }

    return (
        <div className="h-full flex flex-col bg-surface">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-line">
                <span className="text-sm font-medium text-body">{t('Node library', '节点库')} ({categories.reduce((acc, c) => acc + c.nodes.length, 0)})</span>
                <button onClick={onCollapse} className="p-1 hover:bg-hover rounded" aria-label={t('Collapse node library', '收起节点库')}>
                    <ChevronLeft size={14} className="text-muted" />
                </button>
            </div>

            {/* Category Tabs */}
            <div className="flex flex-col border-b border-line max-h-[40%] overflow-y-auto">
                {categories.map((category) => {
                    const Icon = getCategoryIcon(category.name);
                    const color = getCategoryColor(category.name);
                    const isActive = activeCategory === category.name;
                    return (
                        <button
                            key={category.name}
                            onClick={() => setActiveCategory(category.name)}
                            className={`flex items-center gap-2 px-3 py-2 text-xs transition-colors ${isActive
                                    ? 'bg-hover text-ink border-l-2'
                                    : 'text-muted hover:bg-subtle border-l-2 border-transparent'
                                }`}
                            style={{ borderColor: isActive ? color : 'transparent' }}
                        >
                            <Icon size={14} style={{ color }} />
                            <span className="truncate flex-1 text-left">{category.name}</span>
                            <span className="text-muted text-[10px]">{category.nodes.length}</span>
                        </button>
                    );
                })}
            </div>

            {/* Node List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {activeNodes.map((node) => (
                    <div
                        key={node.type}
                        draggable
                        onDragStart={(e) => onDragStart(e, node)}
                        className="group p-2 bg-subtle hover:bg-hover border border-line rounded-lg cursor-grab active:cursor-grabbing transition-colors"
                        title={node.description}
                    >
                        <div className="text-sm text-ink font-medium">{node.name}</div>
                        <div className="text-[10px] text-muted mt-0.5 truncate">
                            {node.description || `${node.io.inputs.length} ${t('in', '输入')} → ${node.io.outputs.length} ${t('out', '输出')}`}
                        </div>
                    </div>
                ))}
                {activeNodes.length === 0 && (
                    <div className="text-center text-xs text-muted py-4">
                        {t('No nodes in this category', '该分类下暂无节点')}
                    </div>
                )}
            </div>

        </div>
    );
}
