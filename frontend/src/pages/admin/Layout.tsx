import {
  ExternalLink,
  HelpCircle,
  Inbox,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Tent,
} from "lucide-react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router";

import { Spinner } from "@/components/ui";
import { admin, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/admin/inbox", label: "Handoffs", icon: Inbox, end: false },
  { to: "/admin/unanswered", label: "Unanswered", icon: HelpCircle, end: false },
  { to: "/admin/conversations", label: "Conversations", icon: MessagesSquare, end: false },
];

export function AdminLayout() {
  const navigate = useNavigate();
  const session = useAsync(admin.session);

  if (session.loading) return <Spinner label="Checking your session" />;
  if (session.error) {
    const status = session.error instanceof ApiError ? session.error.status : 0;
    if (status === 401 || status === 404) return <Navigate to="/admin/login" replace />;
  }

  async function signOut() {
    await admin.logout().catch(() => undefined);
    navigate("/admin/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-zinc-50 md:flex">
      <aside className="border-b border-zinc-200 bg-white md:sticky md:top-0 md:flex md:h-screen md:w-60 md:flex-col md:border-r md:border-b-0">
        <div className="flex h-14 items-center gap-2 px-4 font-semibold tracking-tight">
          <span className="flex size-7 items-center justify-center rounded-md bg-brand-700 text-white">
            <Tent className="size-4" aria-hidden />
          </span>
          Support
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex shrink-0 items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium",
                  isActive
                    ? "bg-zinc-100 text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
                )
              }
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto hidden space-y-1 border-t border-zinc-100 p-3 md:block">
          <a
            href="/"
            className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
          >
            <ExternalLink className="size-4" aria-hidden />
            View store
          </a>
          <button
            type="button"
            onClick={() => void signOut()}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900"
          >
            <LogOut className="size-4" aria-hidden />
            Sign out
          </button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-8 sm:px-8">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight text-zinc-900">{title}</h1>
      {description && <p className="mt-1 text-sm text-zinc-500">{description}</p>}
    </div>
  );
}
