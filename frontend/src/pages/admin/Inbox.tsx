import { CheckCircle2, Inbox as InboxIcon } from "lucide-react";
import { useState } from "react";

import { Card, EmptyState, ErrorMessage, Spinner } from "@/components/ui";
import { admin } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { cn } from "@/lib/utils";

import { PageHeader } from "./Layout";
import { HandoffRow } from "./shared";

export function Inbox() {
  const [showResolved, setShowResolved] = useState(false);
  const handoffs = useAsync(() => admin.handoffs(showResolved), [showResolved]);

  return (
    <>
      <PageHeader
        title="Handoffs"
        description="Conversations the assistant passed to your team, with a summary of what the customer needs."
      />
      <div className="mb-4 inline-flex rounded-lg border border-zinc-200 bg-white p-0.5 text-sm">
        {[
          { value: false, label: "Open" },
          { value: true, label: "Resolved" },
        ].map((tab) => (
          <button
            key={tab.label}
            type="button"
            onClick={() => setShowResolved(tab.value)}
            className={cn(
              "rounded-md px-3 py-1.5 font-medium",
              showResolved === tab.value ? "bg-zinc-100 text-zinc-900" : "text-zinc-500",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <Card>
        {handoffs.error ? (
          <div className="p-4">
            <ErrorMessage error={handoffs.error} onRetry={handoffs.reload} />
          </div>
        ) : handoffs.loading && !handoffs.data ? (
          <Spinner />
        ) : handoffs.data?.length ? (
          <ul className="divide-y divide-zinc-100">
            {handoffs.data.map((h) => (
              <HandoffRow key={h.id} handoff={h} onResolved={handoffs.reload} />
            ))}
          </ul>
        ) : showResolved ? (
          <EmptyState
            icon={CheckCircle2}
            title="Nothing resolved yet"
            description="Handoffs you mark as resolved are kept here."
          />
        ) : (
          <EmptyState
            icon={InboxIcon}
            title="All caught up"
            description="Refunds, complaints and requests for a person will show up here."
          />
        )}
      </Card>
    </>
  );
}
