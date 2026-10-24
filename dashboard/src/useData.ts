import { useCallback, useEffect, useState } from "react";

interface Loaded<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

/** Load data with a stable `load` function, and reload it every `refreshMs` if given. */
export function useData<T>(
  load: () => Promise<T>,
  refreshMs: number | null,
): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  useEffect(() => {
    let live = true;
    load().then(
      (data) => {
        if (live) setState({ data });
      },
      (error: unknown) => {
        if (live)
          setState((old) => ({
            ...old,
            error: error instanceof Error ? error.message : String(error),
          }));
      },
    );
    return () => {
      live = false;
    };
  }, [load, version]);

  useEffect(() => {
    if (refreshMs === null) return;
    const timer = setInterval(reload, refreshMs);
    return () => {
      clearInterval(timer);
    };
  }, [refreshMs, reload]);

  return { data: state.data, error: state.error, reload };
}
