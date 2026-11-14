import { HelpCircle } from "lucide-react";
import { Link } from "react-router";

import { Card, EmptyState, ErrorMessage, Spinner } from "@/components/ui";
import { admin } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { timeAgo } from "@/lib/utils";

import { PageHeader } from "./Layout";

export function Unanswered() {
  const questions = useAsync(admin.unanswered);

  return (
    <>
      <PageHeader
        title="Unanswered questions"
        description="Customers asked these and your help content had no answer. Add the answers to your policy files and the assistant will handle them next time."
      />
      <Card>
        {questions.error ? (
          <div className="p-4">
            <ErrorMessage error={questions.error} onRetry={questions.reload} />
          </div>
        ) : questions.loading ? (
          <Spinner />
        ) : questions.data?.length ? (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-100 text-xs text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Question</th>
                <th className="w-36 px-5 py-3 font-medium">Asked</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {questions.data.map((q) => (
                <tr key={q.id} className="hover:bg-zinc-50">
                  <td className="px-5 py-3">
                    <Link
                      to={`/admin/conversations/${q.conversation_id}`}
                      className="text-zinc-900 hover:text-brand-700"
                    >
                      {q.question}
                    </Link>
                  </td>
                  <td className="px-5 py-3 text-zinc-500">{timeAgo(q.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState
            icon={HelpCircle}
            title="No gaps found yet"
            description="When a customer asks something your policies don't cover, it will appear here."
          />
        )}
      </Card>
    </>
  );
}
