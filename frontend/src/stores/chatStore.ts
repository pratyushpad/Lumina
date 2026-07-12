import { create } from "zustand";
import type { Citation, Message, StreamMeta } from "@/types";

interface ChatStore {
  messages: Record<string, Message[]>;
  streamingContent: string;
  streamingCitations: Citation[];
  streamingMeta: StreamMeta | null;
  isStreaming: boolean;
  setMessages: (sessionId: string, m: Message[]) => void;
  addMessage: (sessionId: string, m: Message) => void;
  setStreaming: (v: boolean) => void;
  appendToken: (t: string) => void;
  setStreamingCitations: (c: Citation[]) => void;
  setStreamingMeta: (m: StreamMeta) => void;
  clearStream: () => void;
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: {},
  streamingContent: "",
  streamingCitations: [],
  streamingMeta: null,
  isStreaming: false,
  setMessages: (sessionId, m) =>
    set((s) => ({ messages: { ...s.messages, [sessionId]: m } })),
  addMessage: (sessionId, m) =>
    set((s) => ({
      messages: { ...s.messages, [sessionId]: [...(s.messages[sessionId] || []), m] },
    })),
  setStreaming: (v) => set({ isStreaming: v }),
  appendToken: (t) => set((s) => ({ streamingContent: s.streamingContent + t })),
  setStreamingCitations: (c) => set({ streamingCitations: c }),
  setStreamingMeta: (m) => set({ streamingMeta: m }),
  clearStream: () =>
    set({ streamingContent: "", streamingCitations: [], streamingMeta: null, isStreaming: false }),
}));
