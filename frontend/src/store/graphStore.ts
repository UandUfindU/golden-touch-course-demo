import { create } from 'zustand';
import { addEdge, applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import type { Node, Edge, OnNodesChange, OnEdgesChange, OnConnect } from '@xyflow/react';

export interface StrategyContext {
    constants?: Record<string, unknown>;
    expressions?: Record<string, unknown>;
}

export interface GraphState {
    strategyContext: StrategyContext;
    graphVersion: number;
    nodes: Node[];
    edges: Edge[];
    onNodesChange: OnNodesChange;
    onEdgesChange: OnEdgesChange;
    onConnect: OnConnect;
    setGraph: (nodes: Node[], edges: Edge[], context?: StrategyContext) => void;
    addNode: (node: Node) => void;
    deleteNode: (nodeId: string) => void;
    deleteEdge: (edgeId: string) => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
    nodes: [],
    strategyContext: {},
    graphVersion: 0,
    edges: [],

    onNodesChange: (changes) => {
        set({
            nodes: applyNodeChanges(changes, get().nodes),
        });
    },

    onEdgesChange: (changes) => {
        set({
            edges: applyEdgeChanges(changes, get().edges),
        });
    },

    onConnect: (connection) => {
        set({
            edges: addEdge(connection, get().edges),
        });
    },

    setGraph: (nodes, edges, strategyContext = {}) => {
        set(state => ({ nodes, edges, strategyContext, graphVersion: state.graphVersion + 1 }));
    },

    addNode: (node) => {
        set({
            nodes: [...get().nodes, node],
        });
    },

    deleteNode: (nodeId) => {
        set({
            nodes: get().nodes.filter((n) => n.id !== nodeId),
            edges: get().edges.filter((e) => e.source !== nodeId && e.target !== nodeId),
        });
    },

    deleteEdge: (edgeId) => {
        set({
            edges: get().edges.filter((e) => e.id !== edgeId),
        });
    },
}));
