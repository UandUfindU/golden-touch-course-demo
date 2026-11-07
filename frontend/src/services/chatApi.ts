import type { Node, Edge } from '@xyflow/react';
import { useGraphStore, type StrategyContext } from '../store/graphStore';
import { useChatStore } from '../store/chatStore';
import { postSse } from './sse';

const API_BASE = '/api/v1';

interface SendMessageOptions {
    sessionId: string;
    message: string;
    layer?: string;
    mode?: string;
    model?: string;
    clientContext?: Record<string, unknown>;
}

export async function sendMessage(options: SendMessageOptions) {
    const { addMessage, setStatus, setIsStreaming } = useChatStore.getState();
    const { setGraph } = useGraphStore.getState();

    setIsStreaming(true);
    addMessage({ role: 'user', content: options.message });

    try {
        for await (const event of postSse(`${API_BASE}/chat/send`, {
            session_id: options.sessionId,
            message: options.message,
            layer: options.layer || 'offline',
            mode: options.mode || 'auto',
            model: options.model,
            client_context: options.clientContext || {},
        })) {
            handleSSEEvent(event, { addMessage, setStatus, setGraph });
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessage({ role: 'system', content: `Error: ${error}` });
    } finally {
        setIsStreaming(false);
        setStatus(null);
    }
}

function handleSSEEvent(
    event: Record<string, unknown>,
    handlers: {
        addMessage: (msg: { role: 'user' | 'assistant' | 'system'; content: string; source?: string }) => void;
        setStatus: (status: string | null) => void;
        setGraph: (nodes: Node[], edges: Edge[], context: StrategyContext) => void;
    }
) {
    const { addMessage, setStatus, setGraph } = handlers;

    switch (event.type) {
        case 'status':
            setStatus(event.content as string);
            break;
        case 'message':
            if (event.source === 'tool:build_strategy' && event.content === 'Invoking build_strategy...') break;
            addMessage({
                role: 'assistant',
                content: event.content as string,
                source: event.source as string,
            });
            break;
        case 'graph_generated': {
            const graph = event.dag as StrategyContext & { nodes?: StrategyNode[]; edges?: StrategyEdge[] };
            if (graph?.nodes && graph?.edges) {
                setGraph(convertStrategyNodes(graph.nodes, graph.edges), convertDagEdgesToReactFlow(graph.edges), {
                    constants: graph.constants,
                    expressions: graph.expressions,
                });
            }
            if (event.final_answer) {
                // final_answer can be string or array - handle both
                let answerText = '';
                if (typeof event.final_answer === 'string') {
                    answerText = event.final_answer;
                } else if (Array.isArray(event.final_answer)) {
                    // Extract assistant messages from conversation array
                    const lastAssistant = (event.final_answer as Array<{ role: string; content: string }>)
                        .filter(m => m.role === 'assistant')
                        .pop();
                    answerText = lastAssistant?.content || 'Strategy generated successfully.';
                } else {
                    answerText = 'Strategy graph generated.';
                }
                addMessage({
                    role: 'assistant',
                    content: answerText,
                    source: 'tool:build_strategy',
                });
            }
            break;
        }
        case 'tool_call':
            setStatus(`🔧 Calling tool: ${event.name}...`);
            break;
        case 'error':
            addMessage({ role: 'system', content: `❌ ${event.content}` });
            break;
        case 'command':
            // Handle commands like run_backtest
            console.log('Received command:', event.action);
            break;
    }
}

type StrategyNode = { id: string; type: string; data?: Record<string, unknown> };

type StrategyEdge = {
    source: string;
    target: string;
    source_port?: string;
    target_port?: string;
    type?: string;
};

export function serializeStrategy(nodes: Node[], edges: Edge[], context: StrategyContext) {
    return {
        ...context,
        nodes: nodes.map(node => ({
            id: node.id,
            type: node.data.nodeType || 'custom',
            data: node.data.params || {},
        })),
        edges: edges.map(edge => ({
            source: edge.source,
            target: edge.target,
            source_port: edge.sourceHandle?.replace(/^output_/, '') || 'default',
            target_port: edge.targetHandle?.replace(/^input_/, '') || 'default',
            type: edge.type === 'smoothstep' ? 'control' : 'data',
        })),
    };
}

function convertStrategyNodes(nodes: StrategyNode[], edges: StrategyEdge[]): Node[] {
    const layouts = new Map(nodes.map(node => [node.id, {
        inputs: new Set<string>(),
        outputs: new Set<string>(),
        downstream: [] as string[],
        remaining: 0,
        column: 0,
    }]));
    for (const edge of edges) {
        const source = layouts.get(edge.source);
        const target = layouts.get(edge.target);
        if (!source || !target) continue;
        source.outputs.add(edge.source_port || 'default');
        source.downstream.push(edge.target);
        target.inputs.add(edge.target_port || 'default');
        target.remaining += 1;
    }

    // Place each rule after all its dependencies so the strategy reads left to right.
    const ready = Array.from(layouts.keys()).filter(id => layouts.get(id)?.remaining === 0);
    for (const id of ready) {
        const layout = layouts.get(id)!;
        for (const targetId of layout.downstream) {
            const target = layouts.get(targetId)!;
            target.column = Math.max(target.column, layout.column + 1);
            target.remaining -= 1;
            if (target.remaining === 0) ready.push(targetId);
        }
    }

    const columns = new Map<number, string[]>();
    for (const [id, { column }] of layouts) {
        const group = columns.get(column) ?? [];
        group.push(id);
        columns.set(column, group);
    }

    return nodes.map(node => {
        const { column, inputs, outputs } = layouts.get(node.id)!;
        const group = columns.get(column)!;
        const io = {
            inputs: Array.from(inputs, name => ({ name, type: 'any' })),
            outputs: Array.from(outputs, name => ({ name, type: 'any' })),
        };

        return {
            id: node.id,
            type: 'custom',
            position: { x: column * 260, y: (group.indexOf(node.id) - (group.length - 1) / 2) * 170 },
            data: { label: node.type, nodeType: node.type, io, params: node.data || {} },
        };
    });
}

function convertDagEdgesToReactFlow(dagEdges: StrategyEdge[]): Edge[] {
    return dagEdges.map((edge, index) => {
        const id = `${edge.source}-${edge.target}-${index}`;
        return {
            id,
            source: edge.source,
            target: edge.target,
            // Map DAG ports to React Flow handles (CustomNode expects input_X / output_Y)
            sourceHandle: `output_${edge.source_port || 'default'}`,
            targetHandle: `input_${edge.target_port || 'default'}`,
            type: edge.type === 'control' ? 'smoothstep' : 'default',
            animated: edge.type === 'control',
            style: edge.type === 'control' ? { stroke: 'var(--color-control)' } : { stroke: 'var(--color-brand)' },
        };
    });
}
