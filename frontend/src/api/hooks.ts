import { useEffect, useState } from 'react';
import { apiGet } from './client';

export interface ApiState<T> { data: T | undefined; error: Error | undefined; loading: boolean }

/**
 * Fetch `path` (or nothing when null). Ignores responses for stale paths.
 * `fresh` skips the cache (per-user data); bump `reloadKey` to refetch.
 */
export function useApi<T>(path: string | null, opts: { fresh?: boolean; reloadKey?: unknown } = {}): ApiState<T> {
  const [state, setState] = useState<ApiState<T>>({ data: undefined, error: undefined, loading: !!path });
  useEffect(() => {
    if (!path) {
      setState({ data: undefined, error: undefined, loading: false });
      return;
    }
    let live = true;
    setState(s => ({ data: s.data, error: undefined, loading: true }));
    apiGet<T>(path, { fresh: opts.fresh }).then(
      data => live && setState({ data, error: undefined, loading: false }),
      error => live && setState({ data: undefined, error, loading: false }),
    );
    return () => { live = false; };
  }, [path, opts.fresh, opts.reloadKey]);   // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
