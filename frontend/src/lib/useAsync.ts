import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => void;
}

interface Settled<T> {
  key: string;
  data?: T;
  error?: Error;
}

/**
 * Runs `load` on mount and whenever `deps` change, with a manual `reload`.
 * Previous data stays visible while a reload is in flight.
 */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [version, setVersion] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ key: "" });
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  const key = JSON.stringify([...deps, version]);

  useEffect(() => {
    let cancelled = false;
    loadRef.current().then(
      (data) => {
        if (!cancelled) setSettled({ key, data });
      },
      (err: unknown) => {
        if (!cancelled) {
          setSettled((prev) => ({
            key,
            data: prev.data,
            error: err instanceof Error ? err : new Error(String(err)),
          }));
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  const current = settled.key === key;
  return {
    data: settled.data,
    error: current ? settled.error : undefined,
    loading: !current,
    reload,
  };
}
