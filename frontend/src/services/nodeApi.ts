/**
 * Node API Service
 * Fetches node definitions from the backend for the visual editor
 */

export interface HandleDefinition {
    name: string;
    type: string;
    description?: string;
}

export interface NodeIOSchema {
    inputs: HandleDefinition[];
    outputs: HandleDefinition[];
}

export interface NodeDefinition {
    type: string;
    name: string;
    category: string;
    description: string;
    scopes: string[];
    io: NodeIOSchema;
    color?: string;
}

const API_BASE = '/api/v1';

// Map categories to colors
const categoryColors: Record<string, string> = {
    'data': '#06b6d4',
    'indicator': '#3b82f6',
    'condition': '#f59e0b',
    'logic': '#f59e0b',
    'signal': '#10b981',
    'backtest': '#8b5cf6',
    'execution': '#8b5cf6',
    'agent': '#ec4899',
    'tool': '#64748b',
    'engine': '#8b5cf6',
    'structure': '#64748b',
    'workflow': '#a855f7',
    'core': '#64748b',
};

function getCategoryColor(category: string): string {
    const lowerCat = category.toLowerCase();
    for (const [key, color] of Object.entries(categoryColors)) {
        if (lowerCat.includes(key)) return color;
    }
    return '#6366f1';
}

// Parse backend schema format to frontend format
function parseIOSchema(inputSchema: Record<string, unknown>, outputSchema: Record<string, unknown>): NodeIOSchema {
    const inputs: HandleDefinition[] = [];
    const outputs: HandleDefinition[] = [];

    // Parse input properties
    const inputProps = (inputSchema?.properties || {}) as Record<string, Record<string, string>>;
    for (const [name, def] of Object.entries(inputProps)) {
        inputs.push({
            name,
            type: def?.type || 'any',
            description: def?.description || '',
        });
    }

    // Parse output properties
    const outputProps = (outputSchema?.properties || {}) as Record<string, Record<string, string>>;
    for (const [name, def] of Object.entries(outputProps)) {
        outputs.push({
            name,
            type: def?.type || 'any',
            description: def?.description || '',
        });
    }

    return { inputs, outputs };
}

export async function fetchNodes(): Promise<NodeDefinition[]> {
    try {
        const response = await fetch(`${API_BASE}/nodes/`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const rawNodes = await response.json();

        return rawNodes.map((node: Record<string, unknown>) => {
            const category = node.category as string || '';
            const io = parseIOSchema(
                node.input_schema as Record<string, unknown> || {},
                node.output_schema as Record<string, unknown> || {}
            );

            return {
                type: node.name as string,
                name: node.name as string,
                category,
                description: node.description as string || '',
                scopes: (node.scopes as string[]) || [],
                io,
                color: getCategoryColor(category),
            };
        });
    } catch (error) {
        console.error('Failed to fetch nodes:', error);
        return [];
    }
}

export function groupNodesByCategory(nodes: NodeDefinition[]): { name: string; color: string; nodes: NodeDefinition[] }[] {
    const categories: Record<string, { color: string; nodes: NodeDefinition[] }> = {};

    for (const node of nodes) {
        if (!categories[node.category]) {
            categories[node.category] = { color: node.color || '#6366f1', nodes: [] };
        }
        categories[node.category].nodes.push(node);
    }

    return Object.entries(categories).map(([name, data]) => ({
        name,
        color: data.color,
        nodes: data.nodes,
    }));
}
