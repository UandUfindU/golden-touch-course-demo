import { useText } from '../i18n';
import { useCallback, useEffect, useState } from 'react';
import type { DragEvent, MouseEvent } from 'react';
import { ReactFlow, Background, Controls, MiniMap, BackgroundVariant, useNodesInitialized, useReactFlow } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import { useGraphStore } from '../store/graphStore';
import CustomNode from './CustomNode';
import { Trash2 } from 'lucide-react';

const nodeTypes = {
    custom: CustomNode,
};

interface ContextMenuState {
    visible: boolean;
    x: number;
    y: number;
    nodeId: string | null;
    edgeId: string | null;
}

export default function GraphCanvas() {
    const t = useText();
    const { nodes, edges, graphVersion, onNodesChange, onEdgesChange, onConnect, addNode, deleteNode, deleteEdge } = useGraphStore();
    const [contextMenu, setContextMenu] = useState<ContextMenuState>({
        visible: false, x: 0, y: 0, nodeId: null, edgeId: null
    });

    const nodesInitialized = useNodesInitialized();
    const { fitView, screenToFlowPosition } = useReactFlow();

    useEffect(() => {
        if (nodesInitialized) void fitView({ padding: 0.16, maxZoom: 1 });
    }, [fitView, graphVersion, nodesInitialized]);

    const onDragOver = useCallback((event: DragEvent) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback(
        (event: DragEvent) => {
            event.preventDefault();

            const data = event.dataTransfer.getData('application/reactflow');
            if (!data) return;

            const { type, label, io } = JSON.parse(data);

            const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
            const newNode = {
                id: `${type}_${Date.now()}`,
                type: 'custom',
                position,
                data: {
                    label,
                    nodeType: type,
                    io,
                    params: {},
                },
            };

            addNode(newNode);
        },
        [addNode, screenToFlowPosition]
    );

    const onNodeContextMenu = useCallback((event: MouseEvent, node: Node) => {
        event.preventDefault();
        setContextMenu({
            visible: true,
            x: event.clientX,
            y: event.clientY,
            nodeId: node.id,
            edgeId: null,
        });
    }, []);

    const onEdgeContextMenu = useCallback((event: MouseEvent, edge: Edge) => {
        event.preventDefault();
        setContextMenu({
            visible: true,
            x: event.clientX,
            y: event.clientY,
            nodeId: null,
            edgeId: edge.id,
        });
    }, []);

    const handleDelete = useCallback(() => {
        if (contextMenu.nodeId) {
            deleteNode(contextMenu.nodeId);
        }
        if (contextMenu.edgeId) {
            deleteEdge(contextMenu.edgeId);
        }
        setContextMenu({ visible: false, x: 0, y: 0, nodeId: null, edgeId: null });
    }, [contextMenu.nodeId, contextMenu.edgeId, deleteNode, deleteEdge]);

    const closeContextMenu = useCallback(() => {
        setContextMenu({ visible: false, x: 0, y: 0, nodeId: null, edgeId: null });
    }, []);

    return (
        <div className="w-full h-full relative" onClick={closeContextMenu}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onDragOver={onDragOver}
                onDrop={onDrop}
                onNodeContextMenu={onNodeContextMenu}
                onEdgeContextMenu={onEdgeContextMenu}
                nodeTypes={nodeTypes}
                deleteKeyCode={['Backspace', 'Delete']}
                fitView
                className="bg-canvas"
            >
                <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--color-line-strong)" />
                {nodes.length > 0 && (
                    <>
                        <Controls />
                        <MiniMap nodeColor={() => "var(--color-brand)"} bgColor="var(--color-surface)" maskColor="#d9eddf99" />
                    </>
                )}
            </ReactFlow>

            {/* Context Menu */}
            {contextMenu.visible && (
                <div
                    className="fixed bg-surface border border-line-strong rounded-lg shadow-xl py-1 z-50"
                    style={{ top: contextMenu.y, left: contextMenu.x }}
                >
                    <button
                        onClick={handleDelete}
                        className="flex items-center gap-2 px-4 py-2 text-sm text-red-700 hover:bg-hover w-full text-left"
                    >
                        <Trash2 size={14} />
                        {contextMenu.nodeId ? t('Delete node', '删除节点') : t('Delete connection', '删除连线')}
                    </button>
                </div>
            )}
        </div>
    );
}
