import BacktestModal, { type BacktestResult } from './components/BacktestModal';
import { ReactFlowProvider } from '@xyflow/react';
import { useEffect, useState, useRef } from 'react';
import type { MouseEvent } from 'react';
import { LanguageContext, type Language } from './i18n';
import GraphCanvas from './components/GraphCanvas';
import ChatPanel from './components/ChatPanel';
import NodeSidebar from './components/NodeSidebar';
import MarketSnapshot from './components/MarketSnapshot';
import { ChevronRight, Layers, Workflow, Activity, BarChart3, Play, PanelLeftOpen, Loader2 } from 'lucide-react';
import { useGraphStore, type StrategyContext } from './store/graphStore';
import { useChatStore } from './store/chatStore';
import { serializeStrategy } from './services/chatApi';
import { postSse } from './services/sse';
import type { Node, Edge } from '@xyflow/react';

function createSessionId() {
  return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function languageFromUrl(): Language {
  return new URLSearchParams(window.location.search).get('lang') === 'zh' ? 'zh' : 'en';
}

export default function App() {
  const [language, setLanguage] = useState(languageFromUrl);
  const t = (en: string, zh: string) => language === 'zh' ? zh : en;
  const nextLanguage = language === 'en' ? 'zh' : 'en';
  const languageUrl = new URL(window.location.href);
  languageUrl.searchParams.set('lang', nextLanguage);

  useEffect(() => {
    const syncLanguage = () => setLanguage(languageFromUrl());
    window.addEventListener('popstate', syncLanguage);
    return () => window.removeEventListener('popstate', syncLanguage);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  }, [language]);

  const switchLanguage = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.history.pushState(null, '', languageUrl);
    setLanguage(nextLanguage);
  };

  const [chatOpen, setChatOpen] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { nodes, edges, strategyContext, setGraph } = useGraphStore();
  const isStreaming = useChatStore(state => state.isStreaming);

  const [backtestModalOpen, setBacktestModalOpen] = useState(false);
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestError, setBacktestError] = useState<string>();
  const [backtestStatus, setBacktestStatus] = useState('');

  const [marketOpen, setMarketOpen] = useState(false);
  const [layer, setLayer] = useState<'offline' | 'online'>('offline');
  const [sessionId, setSessionId] = useState(() => createSessionId());
  const strategyGraph = useRef<{ nodes: Node[]; edges: Edge[]; context: StrategyContext }>({ nodes: [], edges: [], context: {} });
  const workflowGraph = useRef<{ nodes: Node[]; edges: Edge[]; context: StrategyContext }>({ nodes: [], edges: [], context: {} });

  const handleNewChat = () => {
    useChatStore.getState().clearMessages();
    setSessionId(createSessionId());
  };

  const handleLayerSwitch = (targetLayer: 'offline' | 'online') => {
    if (isStreaming) return;
    setMarketOpen(false);
    if (layer === targetLayer) return;

    const currentGraph = layer === 'offline' ? strategyGraph : workflowGraph;
    currentGraph.current = { nodes, edges, context: strategyContext };
    const targetGraph = targetLayer === 'offline' ? strategyGraph : workflowGraph;
    setLayer(targetLayer);
    setGraph(targetGraph.current.nodes, targetGraph.current.edges, targetGraph.current.context);
  };

  const canRun = layer === 'offline' && nodes.length > 0 && !isBacktesting && !isStreaming;

  const handleRun = async () => {
    if (!canRun) return;
    setBacktestModalOpen(true);
    setIsBacktesting(true);
    setBacktestError(undefined);
    setBacktestResult(null);
    setBacktestStatus('');

    try {
      for await (const event of postSse('/api/v1/backtest/run', {
        session_id: sessionId,
        graph_json: serializeStrategy(nodes, edges, strategyContext),
      })) {
        if (event.type === 'error') throw new Error(String(event.content));
        if (event.type === 'result') {
          setBacktestResult(event as unknown as BacktestResult);
          return;
        }
        if (event.type === 'status') setBacktestStatus(String(event.content));
      }
      throw new Error(t('The server did not return a result. Try again.', '服务已结束，但没有返回回测结果。请重试。'));
    } catch (error) {
      setBacktestError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <LanguageContext.Provider value={language}>
      <ReactFlowProvider>
        <div className="flex h-screen w-full flex-col bg-page">
          <header className="flex shrink-0 items-center gap-3 border-b border-line bg-surface px-5 py-3">
            <div className="rounded-xl bg-brand-soft p-2 text-brand-ink">
              <Layers size={23} />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight text-ink">Golden Touch</h1>
              <p className="mt-0.5 text-xs text-muted">{t('LLM + Quant Workbench', 'LLM + Quant 策略研究工作台')}</p>
            </div>
            {marketOpen || layer === 'online' ? (
              <span className="ml-auto hidden text-sm text-muted sm:block">
                {marketOpen ? t('Market overview', '市场观察 · 日线截面') : t('Workflow builder', '工作流搭建 · 触发器与步骤')}
              </span>
            ) : (
              <ol className="ml-auto hidden items-center gap-3 text-sm text-body lg:flex">
                <li>{t('01 Describe a strategy', '01 描述策略')}</li><li aria-hidden="true" className="text-quiet">→</li>
                <li>{t('02 Check the rules', '02 检查规则')}</li><li aria-hidden="true" className="text-quiet">→</li>
                <li>{t('03 Run a backtest', '03 运行回测')}</li>
              </ol>
            )}
            <a
              href={languageUrl.pathname + languageUrl.search + languageUrl.hash}
              hrefLang={nextLanguage === 'zh' ? 'zh-CN' : 'en'}
              lang={nextLanguage === 'zh' ? 'zh-CN' : 'en'}
              onClick={switchLanguage}
              className="ml-auto shrink-0 rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-brand-ink hover:bg-subtle lg:ml-3"
            >
              {t('中文', 'English')}
            </a>
          </header>
          <BacktestModal
            isOpen={backtestModalOpen}
            onClose={() => setBacktestModalOpen(false)}
            result={backtestResult}
            isLoading={isBacktesting}
            status={backtestStatus}
            error={backtestError}
          />
          <div className="flex min-h-0 flex-1">
            <nav aria-label={t("Workbench views", "工作台模式")} className="z-20 flex w-20 shrink-0 flex-col items-center gap-3 border-r border-line py-4">
              <button
                onClick={() => handleLayerSwitch('offline')}
                aria-pressed={!marketOpen && layer === 'offline'}
                disabled={isStreaming}
                className={`flex w-[4.25rem] flex-col items-center gap-1 rounded-lg p-2 ${!marketOpen && layer === 'offline' ? 'bg-brand-soft text-brand-ink' : 'text-muted hover:bg-hover'}`}
              >
                <Activity size={20} />
                <span className="text-xs">{t('Strategy', '策略')}</span>
              </button>
              <button
                onClick={() => handleLayerSwitch('online')}
                aria-pressed={!marketOpen && layer === 'online'}
                disabled={isStreaming}
                className={`flex w-[4.25rem] flex-col items-center gap-1 rounded-lg p-2 ${!marketOpen && layer === 'online' ? 'bg-brand-soft text-brand-ink' : 'text-muted hover:bg-hover'}`}
              >
                <Workflow size={20} />
                <span className="whitespace-nowrap text-xs">{t('Workflow', '工作流')}</span>
              </button>
              <button
                onClick={() => setMarketOpen(true)}
                aria-pressed={marketOpen}
                disabled={isStreaming}
                className={`flex w-[4.25rem] flex-col items-center gap-1 rounded-lg p-2 ${marketOpen ? 'bg-brand-soft text-brand-ink' : 'text-muted hover:bg-hover'}`}
              >
                <BarChart3 size={20} />
                <span className="text-xs">{t('Market', '行情')}</span>
              </button>
            </nav>
            {marketOpen && <MarketSnapshot />}
            <div className={marketOpen ? 'hidden' : 'flex min-w-0 flex-1'}>
              <aside className={`flex shrink-0 border-r border-line ${chatOpen ? 'w-[min(20rem,42vw)]' : 'w-10'}`}>
                {chatOpen ? (
                  <ChatPanel onCollapse={() => setChatOpen(false)} layer={layer} sessionId={sessionId} onNewChat={handleNewChat} />
                ) : (
                  <button onClick={() => setChatOpen(true)} className="flex w-full items-center justify-center hover:bg-hover" aria-label={t("Expand chat", "展开聊天")}>
                    <ChevronRight size={16} className="text-muted" />
                  </button>
                )}
              </aside>
              <main className="flex min-w-0 flex-1 flex-col bg-canvas">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-4 py-3">
                  <div>
                    <h2 className="text-sm font-semibold text-ink">{layer === 'offline' ? t('Strategy rules', '策略规则') : t('Workflow', '工作流')}</h2>
                    <p className="text-xs text-muted">{layer === 'offline' ? t('Check the data, indicators, and trade signals', '核对行情、指标与交易信号') : t('Set up triggers and steps', '配置任务与执行步骤')}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => setSidebarOpen(open => !open)}
                      aria-expanded={sidebarOpen}
                      className="flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-body hover:bg-hover"
                    >
                      <PanelLeftOpen size={15} /> {t('Node library', '节点库')}
                    </button>
                    {layer === 'offline' && (
                      <button
                        onClick={handleRun}
                        disabled={!canRun}
                        className="flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover disabled:bg-hover disabled:text-muted"
                      >
                        {isBacktesting ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                        {isBacktesting ? t('Running…', '回测运行中') : t('Run backtest', '运行回测')}
                      </button>
                    )}
                  </div>
                </div>
                <div className="flex min-h-0 flex-1">
                  {sidebarOpen && (
                    <aside className="w-48 shrink-0 border-r border-line">
                      <NodeSidebar onCollapse={() => setSidebarOpen(false)} />
                    </aside>
                  )}
                  <div className="relative min-w-0 flex-1">
                    <GraphCanvas />
                    {nodes.length === 0 && (
                      <div className="pointer-events-none absolute inset-0 grid place-items-center p-5 text-center">
                        <div className="rounded-2xl border border-line bg-surface/95 p-6 shadow-sm">
                          <p className="font-semibold text-ink">{layer === 'offline' ? t('Your strategy will appear here', '策略将在这里显示') : t('Your workflow will appear here', '工作流将在这里显示')}</p>
                          <p className="mt-2 text-sm text-muted">
                            {layer === 'offline' ? t('Describe a strategy on the left, review the rules, and run a backtest.', '在左侧描述策略，生成后检查规则，再运行历史回测。') : t('Describe a task or drag triggers and steps from the node library.', '在左侧描述任务，或从节点库拖入触发器与步骤。')}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </main>
            </div>
          </div>
        </div>
      </ReactFlowProvider>
    </LanguageContext.Provider>
  );
}
