import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { enc } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { RosterRow } from '../../api/types';
import { ChartCanvas, ErrorNote, Loading, Panel, Pills, SeasonSlider, SectionHead } from '../../components/ui';
import { PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { DASH, fmtNum } from '../../lib/format';
import { oneOf, useQueryParam } from '../../lib/useQuery';
import { nameChain, type Franchise } from './geo';
import { TeamPlayoffs } from './TeamPlayoffs';
import { FavoriteButton } from '../../components/account';

const TEAM_STATS = [
  { value: 'w', label: 'Wins' }, { value: 'srs', label: 'SRS (Strength)' }, { value: 'o_rtg', label: 'Off. Rating' },
  { value: 'd_rtg', label: 'Def. Rating' }, { value: 'pace', label: 'Pace' }, { value: 'pts_per_game', label: 'Points/Game' },
] as const;
type TeamStat = typeof TEAM_STATS[number]['value'];

export function TeamDetail({ franchise }: { franchise: Franchise }) {
  const [raw, setStat] = useQueryParam('stat', 'w');
  const stat = oneOf<TeamStat>(raw, TEAM_STATS.map(s => s.value), 'w');
  const rows = franchise.rows;
  const latest = franchise.latest;
  const playoffs = rows.filter(r => r.playoffs).length;
  const chain = nameChain(franchise);

  const config = useMemo<ChartConfiguration>(() => ({
    type: 'line',
    data: { labels: rows.map(r => r.season), datasets: [{
      label: TEAM_STATS.find(s => s.value === stat)!.label, data: rows.map(r => r[stat]),
      borderColor: PALETTE.blue, backgroundColor: PALETTE.blueDim, tension: 0.25, pointRadius: 2, pointHoverRadius: 6,
      borderWidth: 2.5, fill: true,
      // amber segments = playoff seasons
      segment: { borderColor: (c: { p1DataIndex: number }) => (rows[c.p1DataIndex]?.playoffs ? PALETTE.amber : PALETTE.blue) },
    } as never] },
    options: baseOptions({
      plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: {
        afterTitle: (items: { dataIndex: number }[]) => {
          const t = rows[items[0].dataIndex];
          return `${t.team_name} (${t.city}) \u00b7 ${t.w ?? DASH}-${t.l ?? DASH} \u00b7 ${t.playoffs ? 'Made playoffs' : 'Missed playoffs'}`;
        },
      } } },
      scales: { x: axis({ ticks: { maxTicksLimit: 14 } }), y: axis() },
    }),
  }), [rows, stat]);

  return (
    <Panel id="team-panel">
      <div className="player-header">
        <div>
          <h1 className="player-name" id="tc-name">{franchise.displayName}</h1>
          <div className="player-meta" id="tc-meta">
            {franchise.minSeason}&ndash;{franchise.maxSeason} &middot; {rows.length} seasons &middot; {playoffs} playoff appearances &middot;{' '}
            {latest.status !== 'active' ? <span style={{ color: 'var(--chalk-dim)' }}>no longer in the NBA</span> : <>currently &ldquo;{latest.abbr}&rdquo;</>}
            {chain.length > 1 && <><br /><span style={{ opacity: 0.75 }}>{chain.join(' \u2192 ')}</span></>}
          </div>
        </div>
        <div className="form-row">
          <FavoriteButton kind="team" refId={franchise.slug} label={franchise.displayName} />
          <Link className="pill-btn" to={`/compare/teams/${franchise.slug}`}>Compare &rarr;</Link>
        </div>
      </div>
      <Pills options={[...TEAM_STATS]} value={stat} onChange={v => setStat(v)} id="tc-stat-pills" />
      <ChartCanvas config={config} testId="team-chart" />
      <TeamPlayoffs franchise={franchise} />
      <Roster franchise={franchise} />
    </Panel>
  );
}

const ROSTER_COLS: { key: keyof RosterRow; label: string; pct?: boolean; num?: boolean }[] = [
  { key: 'age', label: 'Age' }, { key: 'g', label: 'GP' }, { key: 'gs', label: 'GS' }, { key: 'mp', label: 'MIN', num: true },
  { key: 'pts', label: 'PTS', num: true }, { key: 'trb', label: 'REB', num: true }, { key: 'ast', label: 'AST', num: true },
  { key: 'fg_pct', label: 'FG%', pct: true }, { key: 'x3p_pct', label: '3P%', pct: true }, { key: 'ft_pct', label: 'FT%', pct: true },
];

function Roster({ franchise }: { franchise: Franchise }) {
  const [season, setSeasonRaw] = useQueryParam('roster', String(franchise.maxSeason));
  const seasonNum = Math.min(franchise.maxSeason, Math.max(franchise.minSeason, parseInt(season, 10) || franchise.maxSeason));
  const [slider, setSlider] = useState(seasonNum);
  const [sort, setSort] = useQueryParam('sort', 'pts');
  const [dir, setDir] = useQueryParam('dir', 'desc');
  const [filter, setFilter] = useState('');

  useEffect(() => setSlider(seasonNum), [seasonNum]);
  useEffect(() => {                      // update the URL (and fetch) once the slider settles
    const t = setTimeout(() => setSeasonRaw(String(slider)), 120);
    return () => clearTimeout(t);
  }, [slider, setSeasonRaw]);

  const { data, error } = useApi<RosterRow[]>(`/teams/${enc(franchise.name)}/roster/${seasonNum}`);
  const teamRow = franchise.rows.find(r => r.season === slider);
  const sortKey = oneOf(sort, ROSTER_COLS.map(c => c.key as string), 'pts') as keyof RosterRow;

  const rows = useMemo(() => {
    let list = data ?? [];
    const f = filter.trim().toLowerCase();
    if (f) list = list.filter(p => p.player.toLowerCase().includes(f));
    const val = (p: RosterRow) => (p[sortKey] as number | null) ?? -Infinity;
    return [...list].sort((a, b) => (dir === 'asc' ? val(a) - val(b) : val(b) - val(a)));
  }, [data, filter, sortKey, dir]);

  const clickSort = (key: string) => {
    if (key === sortKey) setDir(dir === 'desc' ? 'asc' : 'desc');
    else { setSort(key); setDir('desc'); }
  };

  return (
    <div className="roster-section">
      <SectionHead title="Roster" small />
      <div className="roster-scoreboard">
        <div className="roster-season-display">
          <span id="roster-season-label">{slider}</span>
          <span className="era-label">{teamRow?.team_name ?? ''}</span>
        </div>
        <SeasonSlider min={franchise.minSeason} max={franchise.maxSeason} value={slider} onChange={setSlider} id="roster-season-slider" />
      </div>
      <div className="lb-controls">
        <input type="search" id="roster-search" placeholder={'Filter roster by name\u2026'} value={filter} onChange={e => setFilter(e.target.value)} />
      </div>
      {error && <ErrorNote error={error} />}
      <div className="table-scroll">
        <table className="lb-table">
          <thead>
            <tr>
              <th style={{ cursor: 'default' }}>Player</th><th style={{ cursor: 'default' }}>Pos</th>
              {ROSTER_COLS.map(c => (
                <th key={c.key} className={c.key === sortKey ? 'sorted' : ''} onClick={() => clickSort(c.key)}>
                  {c.label}{c.key === sortKey ? (dir === 'asc' ? ' \u2191' : ' \u2193') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody id="roster-tbody">
            {rows.map(p => (
              <tr key={p.player_id + p.team}>
                <td className="name-cell"><Link to={`/players/${p.player_id}`}>{p.player}</Link></td>
                <td>{p.pos || DASH}</td>
                {ROSTER_COLS.map(c => {
                  const v = p[c.key] as number | null;
                  return <td key={c.key}>{v == null ? DASH : c.pct ? (v * 100).toFixed(2) + '%' : c.num ? fmtNum(v) : v}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {!data && !error && <Loading />}
        {data && rows.length === 0 && <div className="roster-empty-note">{filter ? 'No players match that filter.' : 'No roster data for this season.'}</div>}
      </div>
    </div>
  );
}
