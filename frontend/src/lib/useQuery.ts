import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * A URL query parameter as React state, so every view setting is part of the
 * link. Values equal to the default are left out of the URL. Pass
 * `{ push: true }` to add a history entry (default replaces, so dragging a
 * slider doesn't flood the back button).
 */
export function useQueryParam(key: string, fallback: string): [string, (v: string, opts?: { push?: boolean }) => void] {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) ?? fallback;
  const set = useCallback((v: string, opts?: { push?: boolean }) => {
    // Start from the live URL, not the snapshot from this render: two updates
    // in the same event (e.g. stat + order) would otherwise overwrite each other.
    const next = new URLSearchParams(window.location.search);
    if (v === fallback || v === '') next.delete(key); else next.set(key, v);
    setParams(next, { replace: !opts?.push });
  }, [key, fallback, setParams]);
  return [value, set];
}

export function useQueryNumber(key: string, fallback: number): [number, (v: number) => void] {
  const [raw, setRaw] = useQueryParam(key, String(fallback));
  const n = parseInt(raw, 10);
  const set = useCallback((v: number) => setRaw(String(v)), [setRaw]);
  return [Number.isFinite(n) ? n : fallback, set];
}

/** Narrow a query value to one of the allowed options. */
export function oneOf<T extends string>(value: string, options: readonly T[], fallback: T): T {
  return (options as readonly string[]).includes(value) ? (value as T) : fallback;
}
