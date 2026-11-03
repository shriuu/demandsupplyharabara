import { useCallback, useEffect, useRef, useState } from "react";

export type Load<T> =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: T };

/** Loads on mount and when `key` changes; `reload` fetches again. Failure shows less (guardrail 12). */
export function useLoad<T>(fetcher: () => Promise<T>, key: string | readonly string[] = "") {
  const [state, setState] = useState<Load<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);
  const latest = useRef(fetcher);
  const keyText = Array.isArray(key) ? key.join("|") : key;
  useEffect(() => {
    latest.current = fetcher;
  });
  useEffect(() => {
    let live = true;
    latest.current().then(
      (data) => live && setState({ status: "ready", data }),
      () => live && setState({ status: "error" }),
    );
    return () => {
      live = false;
    };
  }, [keyText, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { state, reload };
}
