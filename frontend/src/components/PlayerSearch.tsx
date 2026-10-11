import { useEffect, useRef, useState } from 'react';
import { apiGet, enc } from '../api/client';
import type { PlayerSummary } from '../api/types';
import { HofBadge } from './ui';

/** Autocomplete backed by /players?q= (accent-insensitive, best scorers first). */
export function PlayerSearch({ onSelect, placeholder = 'Search a player\u2026 (e.g. Magic Johnson)', initial = '', id }: {
  onSelect: (p: PlayerSummary) => void; placeholder?: string; initial?: string; id?: string;
}) {
  const [q, setQ] = useState(initial);
  const [results, setResults] = useState<PlayerSummary[] | null>(null);
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => setQ(initial), [initial]);

  useEffect(() => {
    const term = q.trim();
    if (!open || !term) { setResults(null); return; }
    let live = true;
    const t = setTimeout(() => {
      apiGet<PlayerSummary[]>(`/players?q=${enc(term)}&limit=12`).then(r => live && setResults(r), () => live && setResults([]));
    }, 150);
    return () => { live = false; clearTimeout(t); };
  }, [q, open]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const pick = (p: PlayerSummary) => { setQ(p.player); setOpen(false); onSelect(p); };

  return (
    <div className="player-search-wrap" ref={wrap}>
      <input type="search" id={id} value={q} placeholder={placeholder} autoComplete="off"
             onChange={e => { setQ(e.target.value); setOpen(true); }}
             onFocus={() => setOpen(true)}
             onKeyDown={e => { if (e.key === 'Enter' && results?.length) pick(results[0]); if (e.key === 'Escape') setOpen(false); }} />
      {open && results && (
        <div className="player-search-results show">
          {results.length === 0 && <div className="psr-item" style={{ cursor: 'default', color: 'var(--chalk-dim)' }}>No players found</div>}
          {results.map(p => (
            <div key={p.player_id} className="psr-item" onMouseDown={e => { e.preventDefault(); pick(p); }}>
              <span>{p.player}{p.hof && <HofBadge />}</span>
              <span className="psr-meta">{p.first_season}&ndash;{p.last_season}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
