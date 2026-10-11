// Thin fetch wrapper with an in-memory cache. Responses are cached per URL for
// the lifetime of the page, so revisiting a player or comparison is instant,
// and concurrent requests for the same URL share one network call.

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
const cache = new Map<string, Promise<unknown>>();

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join('; ') : body.detail;
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText}`);
  }
  return (res.status === 204 ? undefined : res.json()) as Promise<T>;
}

/** GET with caching. Pass {fresh: true} for data that changes (anything per-user). */
export function apiGet<T>(path: string, opts: { fresh?: boolean } = {}): Promise<T> {
  const url = `${API_BASE}/api/v1${path}`;
  if (opts.fresh) return fetch(url, { credentials: 'include' }).then(r => handle<T>(r));
  let req = cache.get(url) as Promise<T> | undefined;
  if (!req) {
    req = fetch(url, { credentials: 'include' }).then(r => handle<T>(r));
    req.catch(() => cache.delete(url));     // don't cache failures
    cache.set(url, req);
  }
  return req;
}

/** POST / PUT / PATCH / DELETE with a JSON body. Never cached. */
export function apiSend<T>(method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, body?: unknown): Promise<T> {
  return fetch(`${API_BASE}/api/v1${path}`, {
    method,
    credentials: 'include',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(r => handle<T>(r));
}

/** {columns, rows} (compact API format) -> array of objects */
export function fromColumns<T>(payload: { columns: string[]; rows: unknown[][] }): T[] {
  return payload.rows.map(r => Object.fromEntries(payload.columns.map((c, i) => [c, r[i]])) as T);
}

export const enc = encodeURIComponent;
