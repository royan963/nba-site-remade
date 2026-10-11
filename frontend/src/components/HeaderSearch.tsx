import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet, enc } from '../api/client';
import type { PlayerSummary } from '../api/types';
import { HofBadge } from './ui';

const IDEAS = ['how many rings does lebron have', 'curry vs harden', 'most points in a playoff game', 'best rebounding guards of the 90s',
               'youngest MVPs'];

type Item = { kind: 'ask' | 'idea'; text: string } | { kind: 'player'; player: PlayerSummary };

/** Compact "ask the stats" box in the header: opens /search, or jumps straight to a player whose name is typed. */
export function HeaderSearch() {
  const [text, setText] = useState('');
  const [open, setOpen] = useState(false);
  const [players, setPlayers] = useState<PlayerSummary[]>([]);
  const [active, setActive] = useState(0);
  const wrap = useRef<HTMLFormElement>(null);
  const navigate = useNavigate();
  const term = text.trim();

  useEffect(() => {                      // players whose names match what's typed (questions rarely match a name)
    if (!open || term.length < 2) { setPlayers([]); return; }
    let live = true;
    const t = setTimeout(() => {
      apiGet<PlayerSummary[]>(`/players?q=${enc(term)}&limit=4`).then(r => live && setPlayers(r), () => live && setPlayers([]));
    }, 150);
    return () => { live = false; clearTimeout(t); };
  }, [term, open]);

  useEffect(() => {
    const close = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const items: Item[] = term
    ? [{ kind: 'ask', text: term }, ...players.map(p => ({ kind: 'player' as const, player: p }))]
    : IDEAS.map(i => ({ kind: 'idea' as const, text: i }));
  useEffect(() => setActive(0), [term, players.length]);

  const pick = (item: Item | undefined) => {
    if (!item) return;
    setOpen(false);
    setText('');
    if (item.kind === 'player') navigate(`/players/${item.player.player_id}`);
    else navigate(`/search?q=${enc(item.text)}`);
  };

  return (
    <form className="header-search" role="search" ref={wrap} onSubmit={e => { e.preventDefault(); pick(items[active]); }}>
      <input type="search" id="header-search" value={text} autoComplete="off" aria-label="Ask about players and stats"
             aria-expanded={open} aria-controls="header-search-list" placeholder="Ask: how many rings does LeBron have?"
             onChange={e => { setText(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
             onKeyDown={e => {
               if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive(a => Math.min(items.length - 1, a + 1)); }
               if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)); }
               if (e.key === 'Escape') setOpen(false);
             }} />
      {open && items.length > 0 && (
        <div className="player-search-results show header-search-list" id="header-search-list" role="listbox">
          {!term && <div className="psr-heading">Try asking</div>}
          {items.map((item, i) => (
            <div key={item.kind === 'player' ? item.player.player_id : `${item.kind}-${item.text}`} role="option" aria-selected={i === active}
                 className={`psr-item ${i === active ? 'active' : ''}`} onMouseEnter={() => setActive(i)}
                 onMouseDown={e => { e.preventDefault(); pick(item); }}>
              {item.kind === 'player'
                ? <><span>{item.player.player}{item.player.hof && <HofBadge />}</span><span className="psr-meta">player &middot; {item.player.first_season}&ndash;{item.player.last_season}</span></>
                : <><span>{item.kind === 'ask' ? <>Ask: <b>{item.text}</b></> : item.text}</span><span className="psr-meta">{item.kind === 'ask' ? 'Enter' : ''}</span></>}
            </div>
          ))}
        </div>
      )}
    </form>
  );
}
