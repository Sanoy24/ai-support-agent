import { ChevronRight, MessagesSquare } from "lucide-react";
import { Link } from "react-router";

import { ChannelBadge } from "@/components/ChannelBadge";
import { Badge, Card, EmptyState, ErrorMessage, Spinner } from "@/components/ui";
import { admin } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { timeAgo } from "@/lib/utils";

import { PageHeader } from "./Layout";

export function Conversations() {
  const conversations = useAsync(admin.conversations);

  return (
    <>
      <PageHeader
        title="Conversations"
        description="Every chat with the assistant, newest first."
      />
      <Card>
        {conversations.error ? (
          <div className="p-4">
            <ErrorMessage error={conversations.error} onRetry={conversations.reload} />
          </div>
        ) : conversations.loading ? (
          <Spinner />
        ) : conversations.data?.length ? (
          <ul className="divide-y divide-zinc-100">
            {conversations.data.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/admin/conversations/${c.id}`}
                  className="flex items-center gap-4 px-5 py-3.5 hover:bg-zinc-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-zinc-900">{c.preview || "(no messages)"}</p>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-500">
                      <ChannelBadge channel={c.channel} />
                      <span>
                        · {c.message_count} messages · {timeAgo(c.updated_at)}
                      </span>
                    </div>
                  </div>
                  {c.handed_off ? (
                    <Badge tone="warning">Handed off</Badge>
                  ) : (
                    <Badge tone="success">Assistant</Badge>
                  )}
                  <ChevronRight className="size-4 text-zinc-400" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={MessagesSquare}
            title="No conversations yet"
            description="Chats from your store's support widget will appear here."
          />
        )}
      </Card>
    </>
  );
}
