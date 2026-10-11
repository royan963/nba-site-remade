import { useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../../api/hooks';
import type { Align, Basis, CompareResponse, CompareSide, PlayerDetail, PlayerSummary } from '../../api/types';
import { PlayerSearch } from '../../components/PlayerSearch';
import { ChartCanvas, ErrorNote, HofBadge, Loading, NoData, Panel, Pills, SeasonSlider, SectionHead } from '../../components/ui';
import { MONO, PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { chartValue, fmtNum, formatStat, type StatFormat } from '../../lib/format';
import { oneOf, useQueryParam } from '../../lib/useQuery';
import { StatBarRow, type StatRowDef } from './StatBars';
import { PlayerHeadToHead } from './HeadToHead';
import { SaveComparison } from '../../components/account';

const SUGGESTED: [string, string, string][] = [
  ['jamesle01', 'jordami01', 'LeBron James vs Michael Jordan'], ['curryst01', 'thompkl01', 'Stephen Curry vs Klay Thompson'],
  ['birdla01', 'johnsma02', 'Larry Bird vs Magic Johnson'], ['duncati01', 'garneke01', 'Tim Duncan vs Kevin Garnett'],
  ['jokicni01', 'embiijo01', 'Nikola Joki\u0107 vs Joel Embiid'],
];
const ALIGNS = [{ value: 'experience', label: 'Years of Experience' }, { value: 'age', label: 'Age' }, { value: 'calendar', label: 'Calendar Season' }] as const;
const BASES = [{ value: 'raw', label: 'Raw box score' }, { value: 'per100', label: 'Per 100 possessions' }, { value: 'index', label: 'Era-adjusted (vs. league)' }] as const;
const BASIS_NOTES: Record<Basis, [string, string]> = {
  raw: ['Raw box score.', 'Numbers as recorded. Faster eras (the 1960s averaged ~125 possessions a game vs. ~100 today) inflate counting stats.'],
  per100: ['Per 100 possessions.', 'Stats per 100 team possessions, which strips out pace. Basketball-Reference only tracks this from 1973-74, so earlier seasons show \u2014.'],
  index: ['Era-adjusted (vs. league).', 'Each stat vs. that season\u2019s league average: 100 = average, 150 = 50% better. Counting stats use per-36-minute rates (minutes weren\u2019t recorded before 1951-52); shooting indexes compare percentages directly.'],
};
const ADVANCED = new Set(['per', 'ws', 'ws_48', 'bpm', 'vorp', 'usg_pct']);
const AWARD_HONORS = new Set(['MVP', 'DPOY', 'MIP', 'ROY', '6MOY', 'Clutch POY', 'ABA MVP', 'ABA ROY', 'BAA ROY', 'NBA Champion', 'Finals MVP']);

function statFormat(key: string): StatFormat {
  if (['fg_pct', 'x3p_pct', 'ft_pct', 'ts_pct'].includes(key)) return 'pct';
  if (['g', 'o_rtg', 'd_rtg'].includes(key)) return 'int';
  if (key.startsWith('i_')) return 'idx';
  if (key === 'ws_48') return 'num3';
  if (key === 'bpm') return 'signed';
  return 'num';
}

export function ComparePlayers({ a, b }: { a?: string; b?: string }) {
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const qs = search.toString() ? `?${search}` : '';
  const { data: pa } = useApi<PlayerDetail>(a ? `/players/${a}` : null);
  const { data: pb } = useApi<PlayerDetail>(b ? `/players/${b}` : null);
  const setA = (p: PlayerSummary) => navigate(`/compare/players/${p.player_id}${b ? `/${b}` : ''}${qs}`);
  const setB = (p: PlayerSummary) => navigate(a ? `/compare/players/${a}/${p.player_id}${qs}` : `/compare/players/${p.player_id}${qs}`);

  return (
    <div id="compare-players">
      <Panel>
        <div className="compare-picker-row">
          <PlayerSearch onSelect={setA} placeholder={'Search player A\u2026'} initial={pa?.player ?? ''} id="cmp-player-search-a" />
          <div className="compare-vs">VS</div>
          <PlayerSearch onSelect={setB} placeholder={'Search player B\u2026'} initial={pb?.player ?? ''} id="cmp-player-search-b" />
        </div>
      </Panel>
      {a && b && a !== b ? <PlayerComparison a={a} b={b} /> : (
        <div className="empty-state" id="cmp-players-empty">
          <div className="big">{a && a === b ? 'Pick two different players' : 'Pick two players to compare'}</div>
          <div>Search above, or try a classic matchup:</div>
          <div className="chart-controls" style={{ marginTop: 14, justifyContent: 'center' }} id="cmp-player-suggestions">
            {SUGGESTED.map(([x, y, label]) => (
              <button key={label} type="button" className="pill-btn" onClick={() => navigate(`/compare/players/${x}/${y}`)}>{label}</button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PlayerComparison({ a, b }: { a: string; b: string }) {
  const [alignRaw, setAlign] = useQueryParam('align', 'experience');
  const align = oneOf<Align>(alignRaw, ['experience', 'age', 'calendar'], 'experience');
  const [basisRaw, setBasis] = useQueryParam('basis', 'raw');
  const basis = oneOf<Basis>(basisRaw, ['raw', 'per100', 'index'], 'raw');
  const [viewRaw, setView] = useQueryParam('view', 'snapshot');
  const view = oneOf(viewRaw, ['snapshot', 'overlay'] as const, 'snapshot');
  const [posRaw, setPosRaw] = useQueryParam('pos', '');
  const { data, error } = useApi<CompareResponse>(`/compare/players?a=${a}&b=${b}&align=${align}&basis=${basis}`);

  const positions = data?.positions ?? [];
  const min = positions[0]?.position ?? 0, max = positions[positions.length - 1]?.position ?? 0;
  // Default: the latest point where both players have a season.
  const defaultPos = useMemo(() => {
    const both = positions.filter(p => p.a && p.b);
    return (both.length ? both[both.length - 1] : positions[positions.length - 1])?.position ?? 0;
  }, [positions]);
  const parsed = parseInt(posRaw, 10);
  const pos = Number.isFinite(parsed) && parsed >= min && parsed <= max ? parsed : defaultPos;
  const entry = positions.find(p => p.position === pos);

  if (error) return <ErrorNote error={error} />;
  if (!data || data.a.player_id !== a || data.b.player_id !== b) return <Loading />;

  const defs: StatRowDef[] = data.stats.map(s => ({ key: s.key, label: s.label, fmt: statFormat(s.key), lowerBetter: s.lower_is_better }));
  const [noteHead, noteBody] = BASIS_NOTES[basis];
  const alignLabel = align === 'experience' ? 'years of experience' : align === 'age' ? 'age' : 'calendar season';

  let note = `Each player's career on one axis, aligned by ${alignLabel}. Switch to Season snapshot to step through one point at a time.`;
  if (view === 'snapshot') {
    const sa = entry?.a, sb = entry?.b;
    note = align === 'experience'
      ? `Comparing Year ${pos} of each player's career \u2014 ${sa?.season ?? '\u2014'} for ${data.a.player}, ${sb?.season ?? '\u2014'} for ${data.b.player}.`
      : align === 'age'
        ? `Comparing age ${pos} for both players \u2014 ${sa?.season ?? 'no season at this age'} for ${data.a.player}, ${sb?.season ?? 'no season at this age'} for ${data.b.player}.`
        : `Comparing the ${pos} season for both players directly.${!sa || !sb ? ' One or both players did not play that season.' : ''}`;
  }

  return (
    <div id="cmp-players-result">
      <Panel>
        <div className="compare-align-controls">
          <span className="pbp-subhead" style={{ margin: 0 }}>Align by</span>
          <Pills options={[...ALIGNS]} value={align} onChange={v => { setAlign(v); setPosRaw(''); }} id="cmp-align-toggle" />
        </div>
        {view === 'snapshot' && max > min && (
          <SeasonSlider min={min} max={max} value={pos} onChange={v => setPosRaw(String(v))} id="cmp-align-slider" />
        )}
        <div id="cmp-align-note" className="section-sub" style={{ marginTop: 10, marginBottom: 0 }}>{note}</div>

        <div className="compare-align-controls cmp-control-row">
          <span className="pbp-subhead" style={{ margin: 0 }}>Stat basis</span>
          <Pills options={[...BASES]} value={basis} onChange={v => setBasis(v)} id="cmp-basis-toggle" />
        </div>
        <div className="era-note" id="cmp-basis-note"><b>{noteHead}</b> {noteBody}</div>

        <div className="compare-align-controls cmp-control-row">
          <span className="pbp-subhead" style={{ margin: 0 }}>View</span>
          <Pills options={[{ value: 'snapshot', label: 'Season snapshot' }, { value: 'overlay', label: 'Career overlay chart' }]}
                 value={view} onChange={v => setView(v)} id="cmp-view-toggle" />
        </div>
        <div className="cmp-control-row">
          <SaveComparison kind="players" a={a} b={b} defaultTitle={`${data.a.player} vs ${data.b.player}`} />
        </div>
      </Panel>

      {view === 'snapshot' ? (
        <div id="cmp-snapshot-view">
          <div className="panel-row">
            <PlayerSeasonCard id="cmp-card-a" player={data.a} side={entry?.a ?? null} />
            <PlayerSeasonCard id="cmp-card-b" player={data.b} side={entry?.b ?? null} />
          </div>
          <Panel>
            <SectionHead title="Stat-by-Stat" small />
            <div id="cmp-stat-table">
              {entry?.a && entry?.b ? (
                <>
                  {defs.filter(d => !ADVANCED.has(d.key)).map(d => <StatBarRow key={d.key} def={d} a={entry.a!.stats[d.key]} b={entry.b!.stats[d.key]} />)}
                  <div className="cmp-stat-subhead">Advanced metrics <span>already league-relative, so they read the same in every mode</span></div>
                  {defs.filter(d => ADVANCED.has(d.key)).map(d => <StatBarRow key={d.key} def={d} a={entry.a!.stats[d.key]} b={entry.b!.stats[d.key]} />)}
                </>
              ) : <NoData>Both players need a season at this position in the comparison to show stat-by-stat detail.</NoData>}
            </div>
          </Panel>
          <PlayerHeadToHead a={data.a.player_id} b={data.b.player_id} season={entry?.a && entry?.b && entry.same_season ? entry.a.season : undefined} />
        </div>
      ) : <Overlay data={data} defs={defs} align={align} />}
    </div>
  );
}

function PlayerSeasonCard({ id, player, side }: { id: string; player: PlayerSummary; side: CompareSide | null }) {
  return (
    <div className="panel compare-player-card" id={id}>
      <div className="cmp-card-name">{player.player}{player.hof && <HofBadge />}</div>
      <div className="cmp-card-meta">{player.pos || '\u2014'} &middot; {player.first_season}&ndash;{player.last_season} ({player.seasons_played} seasons)</div>
      {side ? (
        <>
          <div className="cmp-card-stat-grid">
            {[['Season', side.season], ['Age', side.age ?? '\u2014'], ['Exp. Yr', side.experience],
              ['PPG', fmtNum(side.raw.pts)], ['RPG', fmtNum(side.raw.trb)], ['APG', fmtNum(side.raw.ast)]].map(([l, v]) => (
              <div className="cs-cell" key={l}><div className="v">{v}</div><div className="l">{l}</div></div>
            ))}
          </div>
          <div className="cmp-card-context">
            {side.teams.join(' / ')}
            {side.league.pace != null && ` \u00b7 league pace ${side.league.pace.toFixed(1)}`}
            {side.league.ts_pct != null && ` \u00b7 league TS ${(side.league.ts_pct * 100).toFixed(1)}%`}
          </div>
          {side.honors.length > 0 && (
            <div className="cmp-card-honors">
              {side.honors.map(h => <span key={h} className={`award-pill won ${h === 'All-Star' ? 'allstar-pill' : ''}`}>{AWARD_HONORS.has(h) ? `\u{1F3C6} ${h}` : h}</span>)}
            </div>
          )}
        </>
      ) : <NoData>No matching season for this player at this point in the comparison.</NoData>}
    </div>
  );
}

function Overlay({ data, defs, align }: { data: CompareResponse; defs: StatRowDef[]; align: Align }) {
  const [statRaw, setStat] = useQueryParam('stat', '');
  const def = defs.find(d => d.key === statRaw) ?? defs[0];
  const axisLabel = align === 'experience' ? 'Year of career' : align === 'age' ? 'Age' : 'Season';

  const config = useMemo<ChartConfiguration>(() => {
    const positions = data.positions;
    const series = (side: 'a' | 'b') => positions.map(p => chartValue(def.fmt, p[side]?.stats[def.key]));
    const ds = (label: string, values: (number | null)[], color: string, fill: string) => ({
      label, data: values, borderColor: color, backgroundColor: fill, pointBackgroundColor: color,
      pointRadius: 3, pointHoverRadius: 6, borderWidth: 2.5, tension: 0.25, spanGaps: false,
    });
    const tick = (v: number) => (def.fmt === 'pct' ? v.toFixed(1) + '%' : def.fmt === 'num3' ? v.toFixed(3) : v);
    return {
      type: 'line',
      data: { labels: positions.map(p => p.position), datasets: [
        ds(data.a.player, series('a'), PALETTE.amber, PALETTE.amberDim), ds(data.b.player, series('b'), PALETTE.blue, PALETTE.blueDim)] },
      options: baseOptions({
        plugins: {
          legend: { labels: { color: PALETTE.chalkDim, font: MONO, boxWidth: 12, boxHeight: 12 } },
          tooltip: { ...TOOLTIP, callbacks: {
            title: (items: { label: string }[]) => `${axisLabel} ${items[0].label}`,
            label: (c: { datasetIndex: number; dataIndex: number; dataset: { label: string } }) => {
              const side = positions[c.dataIndex][c.datasetIndex === 0 ? 'a' : 'b'];
              return `${c.dataset.label}: ${formatStat(def.fmt, side?.stats[def.key])}${side ? ` (${side.season}, age ${side.age ?? '\u2014'})` : ''}`;
            },
          } },
        },
        scales: {
          x: axis({ title: { display: true, text: axisLabel, color: PALETTE.chalkDim, font: MONO } }),
          y: axis({ ticks: { callback: tick }, title: { display: true, text: def.label, color: PALETTE.chalkDim, font: MONO } }),
        },
      }),
    };
  }, [data, def, axisLabel]);

  const hasData = data.positions.some(p => p.a?.stats[def.key] != null || p.b?.stats[def.key] != null);
  return (
    <div id="cmp-overlay-view">
      <Panel>
        <SectionHead title="Career Overlay" small />
        <Pills options={defs.map(d => ({ value: d.key, label: d.label }))} value={def.key} onChange={v => setStat(v)} id="cmp-overlay-pills" />
        <ChartCanvas config={config} tall testId="cmp-overlay-chart" />
        {!hasData && <NoData>Neither player has this stat recorded for these seasons.</NoData>}
      </Panel>
    </div>
  );
}
