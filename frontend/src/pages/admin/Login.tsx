import { Tent } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui";
import { admin, ApiError } from "@/lib/api";

export function Login() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(undefined);
    try {
      await admin.login(password);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 404
          ? "The admin dashboard is turned off. Set ADMIN_PASSWORD on the server to enable it."
          : err instanceof Error
            ? err.message
            : "Sign-in failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="flex size-10 items-center justify-center rounded-lg bg-brand-700 text-white">
            <Tent className="size-5" aria-hidden />
          </span>
          <h1 className="mt-4 text-lg font-semibold tracking-tight">Sign in to Support</h1>
          <p className="mt-1 text-sm text-zinc-500">Review handoffs and conversations.</p>
        </div>
        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-xs"
        >
          <div>
            <label htmlFor="password" className="text-sm font-medium text-zinc-700">
              Admin password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 h-9 w-full rounded-lg border border-zinc-200 px-3 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" className="w-full" loading={loading}>
            Sign in
          </Button>
        </form>
      </div>
    </div>
  );
}
