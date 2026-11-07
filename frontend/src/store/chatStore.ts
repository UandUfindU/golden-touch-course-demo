import { create } from 'zustand';

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    source?: string;
    timestamp: Date;
}

export interface ChatState {
    messages: ChatMessage[];
    status: string | null;
    isStreaming: boolean;
    addMessage: (msg: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
    setStatus: (status: string | null) => void;
    setIsStreaming: (streaming: boolean) => void;
    clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
    messages: [],
    status: null,
    isStreaming: false,

    addMessage: (msg) => {
        const newMsg: ChatMessage = {
            ...msg,
            id: crypto.randomUUID(),
            timestamp: new Date(),
        };
        set({ messages: [...get().messages, newMsg] });
    },

    setStatus: (status) => set({ status }),
    setIsStreaming: (isStreaming) => set({ isStreaming }),
    clearMessages: () => set({ messages: [] }),
}));
