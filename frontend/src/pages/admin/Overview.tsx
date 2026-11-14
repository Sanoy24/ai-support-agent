import { HelpCircle, Inbox, MessagesSquare, UserRound, type LucideIcon } from "lucide-react";
import { Link } from "react-router";

import { Card, CardHeader, EmptyState, ErrorMessage, Spinner } from "@/components/ui";
import { admin } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { timeAgo } from "@/lib/utils";

import { PageHeader } from "./Layout";
import { HandoffRow } from "./shared";

function Stat({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm text-zinc-500">{label}</p>
        <Icon className="size-4 text-zinc-400" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
      <p className="mt-1 text-xs text-zinc-500">{hint}</p>
    </Card>
  );
}

export function Overview() {
  const overview = useAsync(admin.overview);
  const handoffs = useAsync(() => admin.handoffs(false));
  const unanswered = useAsync(admin.unanswered);

  if (overview.error) return <ErrorMessage error={overview.error} onRetry={overview.reload} />;
  if (!overview.data) return <Spinner />;
  const o = overview.data;
  const reloadAll = () => {
    overview.reload();
    handoffs.reload();
  };

  return (
    <>
      <PageHeader
        title="Overview"
        description={`Support assistant performance for ${o.store_name}`}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Conversations"
          value={o.total_conversations}
          hint="All time"
          icon={MessagesSquare}
        />
        <Stat
          label="Resolved by assistant"
          value={`${Math.round((1 - o.handed_off_rate) * 100)}%`}
          hint="Conversations with no handoff"
          icon={UserRound}
        />
        <Stat
          label="Waiting for a person"
          value={o.open_handoffs}
          hint="Open handoffs"
          icon={Inbox}
        />
        <Stat
          label="Unanswered questions"
          value={o.unanswered_questions}
          hint="Gaps in your help content"
          icon={HelpCircle}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader
            title="Waiting for a person"
            description="The assistant handed these over with a summary."
            action={
              <Link to="/admin/inbox" className="text-sm text-brand-700 hover:underline">
                View all
              </Link>
            }
          />
          {handoffs.data?.length ? (
            <ul className="divide-y divide-zinc-100">
              {handoffs.data.slice(0, 4).map((h) => (
                <HandoffRow key={h.id} handoff={h} onResolved={reloadAll} />
              ))}
            </ul>
          ) : handoffs.loading ? (
            <Spinner />
          ) : (
            <EmptyState
              icon={Inbox}
              title="All caught up"
              description="Refunds, complaints and requests for a person will show up here."
            />
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Recent unanswered questions"
            description="Add these answers to your policies."
            action={
              <Link to="/admin/unanswered" className="text-sm text-brand-700 hover:underline">
                View all
              </Link>
            }
          />
          {unanswered.data?.length ? (
            <ul className="divide-y divide-zinc-100">
              {unanswered.data.slice(0, 5).map((q) => (
                <li key={q.id} className="px-5 py-3">
                  <Link
                    to={`/admin/conversations/${q.conversation_id}`}
                    className="text-sm text-zinc-900 hover:text-brand-700"
                  >
                    {q.question}
                  </Link>
                  <p className="mt-0.5 text-xs text-zinc-500">{timeAgo(q.created_at)}</p>
                </li>
              ))}
            </ul>
          ) : unanswered.loading ? (
            <Spinner />
          ) : (
            <EmptyState
              icon={HelpCircle}
              title="No gaps found yet"
              description="Questions your help content couldn't answer will appear here."
            />
          )}
        </Card>
      </div>
    </>
  );
}
