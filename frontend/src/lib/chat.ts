export interface Source {
  title: string;
  source: string;
}

export interface ChatReply {
  conversation_id: string;
  reply: string;
  handed_off: boolean;
  sources: Source[];
}

export class ChatError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function sendChatMessage(
  apiBase: string,
  message: string,
  conversationId: string | null,
  signal?: AbortSignal,
): Promise<ChatReply> {
  const response = await fetch(`${apiBase}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
    signal,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail =
      typeof body?.detail === "string" ? body.detail : "Something went wrong. Please try again.";
    throw new ChatError(detail, response.status);
  }
  return (await response.json()) as ChatReply;
}

/** Turns "Returns and Refunds > Return window" into "Return window". */
export function sourceLabel(source: Source): string {
  return source.title.split(" > ").pop() ?? source.title;
}

export function uniqueSourceLabels(sources: Source[], max = 3): string[] {
  return [...new Set(sources.map(sourceLabel))].slice(0, max);
}
