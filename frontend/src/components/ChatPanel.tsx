import { useText } from '../i18n';
import { useState, useRef, useEffect } from 'react';
import { Send, BrainCircuit, Zap, Loader2, ChevronLeft, Plus } from 'lucide-react';
import { useChatStore } from '../store/chatStore';
import { useGraphStore } from '../store/graphStore';
import { sendMessage, serializeStrategy } from '../services/chatApi';

interface ChatPanelProps {
    onCollapse: () => void;
    layer: 'offline' | 'online';
    sessionId: string;
    onNewChat: () => void;
}

export default function ChatPanel({ onCollapse, layer, sessionId, onNewChat }: ChatPanelProps) {
    const t = useText();
    const { messages, status, isStreaming } = useChatStore();
    const { nodes, edges, strategyContext } = useGraphStore();
    const [input, setInput] = useState('');
    const [mode, setMode] = useState<'fast' | 'think'>('fast');
    const [model, setModel] = useState('');
    const [models, setModels] = useState<string[]>([]);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const controller = new AbortController();
        fetch('/api/v1/ai/models', { signal: controller.signal })
            .then(response => {
                if (!response.ok) throw new Error('Could not load models');
                return response.json() as Promise<{ models: string[]; default: string }>;
            })
            .then(config => {
                setModels([...new Set([config.default, ...config.models].filter(Boolean))]);
                setModel(config.default);
            })
            .catch(() => {
                // An empty selection delegates model choice to the chat API.
            });
        return () => controller.abort();
    }, []);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, status]);

    const handleSend = () => {
        if (!input.trim() || isStreaming) return;

        sendMessage({
            sessionId,
            message: input.trim(),
            layer,
            mode,
            model: model || undefined,
            clientContext: nodes.length > 0 ? {
                current_graph_dag: serializeStrategy(nodes, edges, strategyContext),
            } : undefined,
        });

        setInput('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="w-full flex flex-col bg-surface">
            {/* Header */}
            <div className="p-4 border-b border-line flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-ink flex items-center gap-2">
                        <BrainCircuit className="text-brand-ink" />
                        {layer === 'offline' ? t('Strategy assistant', '策略助手') : t('Workflow assistant', '工作流助手')}
                    </h2>
                    <button
                        onClick={() => { onNewChat(); setInput(''); }}
                        disabled={isStreaming}
                        aria-label={t('New chat', '新对话')}
                        className="p-1 hover:bg-hover rounded text-muted hover:text-ink transition-colors"
                        title={t('New chat', '新对话')}
                    >
                        <Plus size={16} />
                    </button>
                </div>
                <button onClick={onCollapse} className="p-1 hover:bg-hover rounded" aria-label={t('Collapse chat', '收起面板')}>
                    <ChevronLeft size={16} className="text-muted" />
                </button>
            </div>

            {/* Mode & Model Selector */}
            <div className="p-3 border-b border-line space-y-2">
                <div className="flex gap-2">
                    <button
                        onClick={() => setMode('fast')}
                        className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${mode === 'fast'
                            ? 'bg-brand text-white'
                            : 'bg-hover text-body hover:bg-hover'
                            }`}
                        aria-label={t('Switch to quick mode', '切换到快速模式')}
                    >
                        <Zap size={12} /> {t('Quick', '快速')}
                    </button>
                    <button
                        onClick={() => setMode('think')}
                        className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center gap-1.5 ${mode === 'think'
                            ? 'bg-brand text-white'
                            : 'bg-hover text-body hover:bg-hover'
                            }`}
                        aria-label={t('Switch to thinking mode', '切换到思考模式')}
                    >
                        <BrainCircuit size={12} /> {t('Think', '思考')}
                    </button>
                </div>

                <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="w-full bg-hover text-ink text-xs rounded-lg px-3 py-1.5 border border-line-strong"
                    aria-label={t('Select model', '选择模型')}
                >
                    {models.length === 0 && <option value="">{t('Default model', '后端默认模型')}</option>}
                    {models.map(option => <option key={option} value={option}>{option}</option>)}
                </select>
            </div>

            {/* Messages */}
            <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-3">
                {messages.length === 0 && (
                    <div className="text-center py-8">
                        <BrainCircuit size={48} className="mx-auto text-quiet mb-3" />
                        <p className="text-sm text-body">{layer === 'offline' ? t('Describe the asset, indicators, and trading rules', '描述标的、指标和交易条件') : t('Describe a trigger and what should happen next', '描述触发方式与任务步骤')}</p>
                        {layer === 'offline' && (
                            <button
                                type="button"
                                disabled={isStreaming}
                                onClick={() => {
                                    setInput(t(
                                        'Build a strategy for AAPL using its last 250 daily bars. Use 10-day and 20-day simple moving averages. Buy when the shorter average crosses above the longer one and sell when it crosses below.',
                                        '请生成一个 AAPL 日线双均线策略。使用最近 250 根日线，计算 10 日和 20 日简单均线，短均线上穿时发出买入信号，下穿时发出卖出信号。',
                                    ));
                                    inputRef.current?.focus();
                                }}
                                className="mt-4 rounded-lg border border-line-strong px-3 py-2 text-sm text-brand-ink hover:bg-brand-soft"
                            >
                                {t('Try the AAPL example', '填入示例 · AAPL 双均线')}
                            </button>
                        )}
                    </div>
                )}

                {messages.map((msg) => (
                    <div
                        key={msg.id}
                        className={`p-3 rounded-xl text-sm ${msg.role === 'user'
                            ? 'bg-brand-soft ml-6'
                            : msg.role === 'system'
                                ? 'bg-red-50 text-red-800'
                                : 'bg-subtle mr-6'
                            }`}
                    >
                        {msg.role === 'assistant' && msg.content.trimStart().startsWith('```python') ? (
                            <>
                                <p>{t('Your strategy is ready. Check the data, indicators, and trade rules on the canvas.', '策略已生成，请核对画布中的行情、指标和买卖条件。')}</p>
                                <details className="mt-2 text-xs text-muted">
                                    <summary className="cursor-pointer">{t('Show the generated rules', '查看模型生成的规则')}</summary>
                                    <pre className="mt-2 whitespace-pre-wrap break-words select-text">{msg.content}</pre>
                                </details>
                            </>
                        ) : (
                            <div className="whitespace-pre-wrap break-words select-text">{msg.content}</div>
                        )}
                    </div>
                ))}

                {status && (
                    <div title={status} className="flex items-center gap-2 text-sm text-brand-ink animate-pulse">
                        <Loader2 className="animate-spin" size={14} />
                        {t('Working on it…', '正在处理…')}
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-line">
                <div className="flex gap-2">
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isStreaming}
                        placeholder={isStreaming ? t('Thinking…', '正在思考…') : layer === 'offline' ? t('Describe your strategy…', '描述你的策略…') : t('Describe your workflow…', '描述你的工作流…')}
                        rows={2}
                        className="flex-1 border border-line bg-subtle rounded-xl px-4 py-2 text-sm text-ink placeholder-muted resize-none focus:outline-none focus:ring-2 focus:ring-brand disabled:opacity-50 disabled:cursor-not-allowed"
                        aria-label={t('Chat message', '聊天输入框')}
                    />
                    <button
                        onClick={handleSend}
                        disabled={isStreaming || !input.trim()}
                        className="px-4 bg-brand hover:bg-brand-hover disabled:bg-hover disabled:cursor-not-allowed rounded-xl text-white transition-colors disabled:text-muted"
                        aria-label={t('Send message', '发送消息')}
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
}
