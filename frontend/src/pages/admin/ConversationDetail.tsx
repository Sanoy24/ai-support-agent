import { ArrowLeft, BookOpen, Wrench } from "lucide-react";
import { Link, useParams } from "react-router";

import { Badge, Card, CardHeader, ErrorMessage, Spinner } from "@/components/ui";
import { admin } from "@/lib/api";
import { uniqueSourceLabels } from "@/lib/chat";
import { categoryLabel } from "@/lib/labels";
import { useAsync } from "@/lib/useAsync";
import { cn, timeAgo } from "@/lib/utils";

const TOOL_LABELS: Record<string, string> = {
  lookup_order: "Looked up order",
  search_help_center: "Searched help content",
  hand_off_to_human: "Handed off",
};

export function ConversationDetail() {
  const { id = "" } = useParams();
  const conversation = useAsync(() => admin.conversation(id), [id]);

  return (
    <>
      <Link
        to="/admin/conversations"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All conversations
      </Link>

      {conversation.error ? (
        <ErrorMessage error={conversation.error} onRetry={conversation.reload} />
      ) : !conversation.data ? (
        <Spinner />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Transcript"
              description={`Started ${timeAgo(conversation.data.created_at)}`}
            />
            <ol className="space-y-4 px-5 py-5">
              {conversation.data.messages.map((m, i) => (
                <li
                  key={i}
                  className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}
                >
                  <div className="max-w-[85%]">
                    <div
                      className={cn(
                        "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                        m.role === "user"
                          ? "rounded-br-md bg-zinc-900 text-white"
                          : "rounded-bl-md bg-zinc-100 text-zinc-900",
                      )}
                    >
                      {m.content}
                    </div>
                    {m.role === "assistant" && (m.tools.length > 0 || m.sources.length > 0) && (
                      <div className="mt-1.5 flex flex-wrap gap-1.5 text-[11px] text-zinc-500">
                        {[...new Set(m.tools)].map((tool) => (
                          <span
                            key={tool}
                            className="inline-flex items-center gap-1 rounded-md bg-white px-1.5 py-0.5 ring-1 ring-zinc-200"
                          >
                            <Wrench className="size-3" aria-hidden />
                            {TOOL_LABELS[tool] ?? tool}
                          </span>
                        ))}
                        {uniqueSourceLabels(m.sources, 4).map((label) => (
                          <span
                            key={label}
                            className="inline-flex items-center gap-1 rounded-md bg-white px-1.5 py-0.5 ring-1 ring-zinc-200"
                          >
                            <BookOpen className="size-3" aria-hidden />
                            {label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </Card>

          <div className="space-y-6">
            <Card className="p-5">
              <p className="text-xs font-medium tracking-wide text-zinc-500 uppercase">Status</p>
              <div className="mt-2">
                {conversation.data.handed_off ? (
                  <Badge tone="warning">Handed to a person</Badge>
                ) : (
                  <Badge tone="success">Handled by assistant</Badge>
                )}
              </div>
              <p className="mt-4 text-xs font-medium tracking-wide text-zinc-500 uppercase">
                Conversation ID
              </p>
              <p className="mt-1 font-mono text-xs break-all text-zinc-700">
                {conversation.data.id}
              </p>
            </Card>

            {conversation.data.handoffs.map((h) => (
              <Card key={h.id} className="p-5">
                <div className="flex items-center justify-between gap-2">
                  <Badge tone="warning">{categoryLabel(h.category)}</Badge>
                  {h.resolved && <Badge tone="success">Resolved</Badge>}
                </div>
                <p className="mt-3 text-sm text-zinc-900">{h.summary}</p>
                <p className="mt-2 text-xs text-zinc-500">{timeAgo(h.created_at)}</p>
              </Card>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
