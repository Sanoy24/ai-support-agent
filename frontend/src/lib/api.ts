import type { Source } from "./chat";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(detail || "Request failed", response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// --- Store -----------------------------------------------------------------

export interface Product {
  sku: string;
  title: string;
  description: string;
  price: number;
  currency: string;
  in_stock: boolean;
  tags: string[];
  url: string | null;
}

export interface StoreInfo {
  name: string;
  products: Product[];
}

export const getStore = () => request<StoreInfo>("/api/store");

// --- Admin -----------------------------------------------------------------

export interface Overview {
  store_name: string;
  total_conversations: number;
  open_handoffs: number;
  unanswered_questions: number;
  handed_off_rate: number;
}

export interface Handoff {
  id: number;
  conversation_id: string;
  category: string;
  summary: string;
  resolved: boolean;
  created_at: string;
}

export interface UnansweredQuestion {
  id: number;
  conversation_id: string;
  question: string;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  handed_off: boolean;
  preview: string;
}

export interface TranscriptMessage {
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  tools: string[];
  created_at: string;
}

export interface Conversation {
  id: string;
  created_at: string;
  handed_off: boolean;
  handoffs: Handoff[];
  messages: TranscriptMessage[];
}

export const admin = {
  login: (password: string) =>
    request<void>("/api/admin/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => request<void>("/api/admin/logout", { method: "POST" }),
  session: () => request<void>("/api/admin/session"),
  overview: () => request<Overview>("/api/admin/overview"),
  handoffs: (resolved = false) => request<Handoff[]>(`/api/admin/handoffs?resolved=${resolved}`),
  resolveHandoff: (id: number) =>
    request<Handoff>(`/api/admin/handoffs/${id}/resolve`, { method: "POST" }),
  unanswered: () => request<UnansweredQuestion[]>("/api/admin/unanswered"),
  conversations: () => request<ConversationSummary[]>("/api/admin/conversations"),
  conversation: (id: string) =>
    request<Conversation>(`/api/admin/conversations/${encodeURIComponent(id)}`),
};
