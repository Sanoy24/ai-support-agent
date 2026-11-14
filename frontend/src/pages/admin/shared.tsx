import { Check } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { Badge, Button } from "@/components/ui";
import { admin, type Handoff } from "@/lib/api";
import { categoryLabel } from "@/lib/labels";
import { timeAgo } from "@/lib/utils";

export function HandoffRow({ handoff, onResolved }: { handoff: Handoff; onResolved: () => void }) {
  const [resolving, setResolving] = useState(false);

  async function resolve() {
    setResolving(true);
    try {
      await admin.resolveHandoff(handoff.id);
      onResolved();
    } finally {
      setResolving(false);
    }
  }

  return (
    <li className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-start">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="warning">{categoryLabel(handoff.category)}</Badge>
          <span className="text-xs text-zinc-500">{timeAgo(handoff.created_at)}</span>
        </div>
        <p className="mt-2 text-sm text-zinc-900">{handoff.summary}</p>
        <Link
          to={`/admin/conversations/${handoff.conversation_id}`}
          className="mt-1 inline-block text-sm text-brand-700 hover:underline"
        >
          Read conversation
        </Link>
      </div>
      {!handoff.resolved && (
        <Button variant="secondary" loading={resolving} onClick={() => void resolve()}>
          <Check className="size-4" aria-hidden />
          Mark resolved
        </Button>
      )}
    </li>
  );
}
