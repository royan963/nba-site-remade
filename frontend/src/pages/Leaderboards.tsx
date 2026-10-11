import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../api/hooks';
import { enc } from '../api/client';
import type { LeaderRow, Meta, PlayoffLeader } from '../api/types';
import { ErrorNote, HofBadge, Loading, Panel, Pills, SectionHead } from '../components/ui';
import { fmtInt, fmtNum } from '../lib/format';
import { oneOf, useQueryParam } from '../lib/useQuery';
import { CoverageNote } from './player/PlayoffPanel';

type Col = { key: string; label: string; dec?: number };

const STATS = [
  { key: 'pts', label: 'Points' }, { key: 'trb', label: 'Rebounds' }, { key: 'ast', label: 'Assists' }, { key: 'stl', label: 'Steals' },
  { key: 'blk', label: 'Blocks' }, { key: 'x3p', label: '3-Pointers Made' }, { key: 'g', label: 'Games Played' },
  { key: 'ppg', label: 'Points / Game (avg)' }, { key: 'rpg', label: 'Rebounds / Game (avg)' }, { key: 'apg', label: 'Assists / Game (avg)' },
  { key: 'ws', label: 'Win Shares' }, { key: 'vorp', label: 'VORP (1974+)' }, { key: 'all_star', label: 'All-Star Selections' },
];
const PLAYOFF_STATS = [
  { key: 'pts', label: 'Points' }, { key: 'trb', label: 'Rebounds' }, { key: 'ast', label: 'Assists' }, { key: 'stl', label: 'Steals' },
  { key: 'blk', label: 'Blocks' }, { key: 'x3p', label: '3-Pointers Made' }, { key: 'g', label: 'Games Played' },
  { key: 'ppg', label: 'Points / Game (25+ games)' }, { key: 'rpg', label: 'Rebounds / Game (25+ games)' }, { key: 'apg', label: 'Assists / Game (25+ games)' },
  { key: 'titles', label: 'Championships' },
];
const COLUMNS: Col[] = [{ key: 'g', label: 'GP' }, { key: 'pts', label: 'PTS' }, { key: 'trb', label: 'REB' }, { key: 'ast', label: 'AST' }, { key: 'ppg', label: 'PPG', dec: 1 }];
const EXTRA: Record<string, Col> = {
  stl: { key: 'stl', label: 'STL' }, blk: { key: 'blk', label: 'BLK' }, x3p: { key: 'x3p', label: '3PM' }, rpg: { key: 'rpg', label: 'RPG', dec: 1 },
  apg: { key: 'apg', label: 'APG', dec: 1 }, ws: { key: 'ws', label: 'WS', dec: 1 }, vorp: { key: 'vorp', label: 'VORP', dec: 1 }, all_star: { key: 'all_star', label: 'ASG' },
};
const PLAYOFF_COLUMNS: Col[] = [
  { key: 'g', label: 'GP' }, { key: 'pts', label: 'PTS' }, { key: 'trb', label: 'REB' }, { key: 'ast', label: 'AST' }, { key: 'stl', label: 'STL' },
  { key: 'blk', label: 'BLK' }, { key: 'x3p', label: '3PM' }, { key: 'ppg', label: 'PPG', dec: 1 }, { key: 'titles', label: '\u{1F3C6}' },
];

export default function Leaderboards() {
  const { data: meta } = useApi<Meta>('/meta');
  const [typeRaw, setType] = useQueryParam('type', 'regular');
  const playoffs = typeRaw === 'playoffs';
  const stats = playoffs ? PLAYOFF_STATS : STATS;
  const [statRaw, setStat] = useQueryParam('stat', 'pts');
  const stat = oneOf(statRaw, stats.map(s => s.key), 'pts');
  const [order, setOrder] = useQueryParam('order', 'desc');
  const [era, setEra] = useQueryParam('era', 'all');
  const [q, setQ] = useQueryParam('q', '');
  const [typed, setTyped] = useState(q);

  useEffect(() => {                       // debounce the name filter
    const t = setTimeout(() => setQ(typed.trim()), 200);
    return () => clearTimeout(t);
  }, [typed, setQ]);

  const path = `${playoffs ? '/leaders/playoffs' : '/leaders'}?stat=${stat}&order=${order === 'asc' ? 'asc' : 'desc'}&era=${enc(era)}&q=${enc(q)}&limit=100`;
  const { data, error, loading } = useApi<(LeaderRow | PlayoffLeader)[]>(path);

  const latest = meta?.latest_season ?? new Date().getFullYear();
  const eras = [
    { value: 'all', label: 'All eras' },
    { value: '1947-1969', label: '1947\u20131969 (Early NBA)' },
    { value: '1970-1989', label: '1970\u20131989 (ABA merger era)' },
    { value: '1990-2009', label: '1990\u20132009 (Jordan to early 3pt)' },
    { value: `2010-${latest}`, label: `2010\u2013${latest} (Modern / 3pt era)` },
  ];
  const cols: Col[] = playoffs ? PLAYOFF_COLUMNS : EXTRA[stat] ? [...COLUMNS, EXTRA[stat]] : COLUMNS;
  const sortBy = (key: string) => {
    if (!stats.some(s => s.key === key)) return;
    if (key === stat) setOrder(order === 'desc' ? 'asc' : 'desc');
    else { setStat(key); setOrder('desc'); }
  };
  const arrow = (key: string) => (key === stat ? (order === 'asc' ? ' \u2191' : ' \u2193') : '');
  const years = meta ? meta.latest_season - meta.first_season + 1 : 80;

  return (
    <section className="view active" id="view-leaders">
      <SectionHead title="All-Time Leaderboards">
        {playoffs ? 'Career playoff totals, from game-by-game box scores.' : `Career regular-season totals across all ${years} seasons.`} Click a column to sort, click a name to open the player.
      </SectionHead>
      <Panel>
        <div className="lb-controls">
          <Pills options={[{ value: 'regular', label: 'Regular season' }, { value: 'playoffs', label: 'Playoffs' }]} value={playoffs ? 'playoffs' : 'regular'}
                 onChange={v => { setType(v); setOrder('desc'); }} id="lb-type" />
          <select id="lb-stat-select" value={stat} onChange={e => { setStat(e.target.value); setOrder('desc'); }}>
            {stats.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <input type="search" id="lb-search" placeholder={'Filter by player name\u2026'} value={typed} onChange={e => setTyped(e.target.value)} />
          <select id="lb-era-select" value={era} onChange={e => setEra(e.target.value)}>
            {eras.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {error && <ErrorNote error={error} />}
        <div className="table-scroll" style={{ opacity: loading ? 0.6 : 1 }}>
          <table className="lb-table" id="lb-table">
            <thead>
              <tr>
                <th>#</th><th>Player</th><th>Pos</th><th>Span</th>
                {cols.map(c => <th key={c.key} className={c.key === stat ? 'sorted' : ''} onClick={() => sortBy(c.key)}>{c.label}{arrow(c.key)}</th>)}
              </tr>
            </thead>
            <tbody id="lb-tbody">
              {data?.map(p => (
                <tr key={p.player_id}>
                  <td className="rank-cell">{p.rank}</td>
                  <td className="name-cell"><Link to={`/players/${p.player_id}`}>{p.player}</Link>{p.hof && <HofBadge />}</td>
                  <td>{p.pos || '\u2014'}</td>
                  <td>{p.first_season}&ndash;{p.last_season}</td>
                  {cols.map(c => {
                    const v = (p as unknown as Record<string, number | null>)[c.key];
                    return <td key={c.key}>{c.dec ? fmtNum(v, c.dec) : fmtInt(v)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {data && data.length === 0 && <div className="no-data-note">No players match.</div>}
          {!data && !error && <Loading />}
        </div>
        {playoffs && <CoverageNote />}
      </Panel>
    </section>
  );
}
