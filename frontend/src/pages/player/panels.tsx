import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../../api/hooks';
import type { PbpSeason, PlayerDetail, PlayerHonors, PlayerPlayoffs, PlayerProjection, PlayerSeason, SimilarResponse } from '../../api/types';
import { ChartCanvas, ErrorNote, HofBadge, Loading, NoData, Panel, Pills, SectionHead } from '../../components/ui';
import { PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { fmtInt, fmtNum, fmtSigned, formatStat, type StatFormat } from '../../lib/format';
import { oneOf, useQueryParam } from '../../lib/useQuery';
import { roleColor } from '../models/archetypeColors';

// ---- Career trajectory chart -------------------------------------------------
const CAREER_STATS: { key: keyof PlayerSeason; label: string; pct?: boolean; signed?: boolean }[] = [
  { key: 'pts', label: 'Points/Game' }, { key: 'trb', label: 'Rebounds/Game' }, { key: 'ast', label: 'Assists/Game' },
  { key: 'stl', label: 'Steals/Game' }, { key: 'blk', label: 'Blocks/Game' }, { key: 'fg_pct', label: 'FG%', pct: true },
  { key: 'x3p_pct', label: '3P%', pct: true }, { key: 'mp', label: 'Minutes/Game' }, { key: 'ts_pct', label: 'TS%', pct: true },
  { key: 'per', label: 'PER' }, { key: 'usg_pct', label: 'Usage %' }, { key: 'ws', label: 'Win Shares' },
  { key: 'bpm', label: 'BPM', signed: true }, { key: 'vorp', label: 'VORP' },
];

const PROJECTABLE = new Set(['pts', 'trb', 'ast', 'mp', 'ts_pct']);

// playoff stat available for each career-chart stat
const PLAYOFF_KEYS: Record<string, keyof PlayerPlayoffs['seasons'][number]> = {
  pts: 'ppg', trb: 'rpg', ast: 'apg', stl: 'spg', blk: 'bpg', mp: 'mpg', fg_pct: 'fg_pct', x3p_pct: 'x3p_pct', ts_pct: 'ts_pct',
};

export function CareerChart({ seasons, projection, playoffs }: { seasons: PlayerSeason[]; projection?: PlayerProjection; playoffs?: PlayerPlayoffs }) {
  const [raw, setStat] = useQueryParam('stat', 'pts');
  const [typeRaw, setType] = useQueryParam('type', 'regular');
  const hasPlayoffs = !!playoffs && playoffs.seasons.length > 0;
  const po = hasPlayoffs && typeRaw === 'playoffs';
  const available = CAREER_STATS.filter(s => !po || s.key in PLAYOFF_KEYS);
  const stat = oneOf(raw, available.map(s => s.key as string), 'pts');
  const def = CAREER_STATS.find(s => s.key === stat)!;
  const config = useMemo<ChartConfiguration>(() => {
    const fmt = (v: number) => (def.pct ? v.toFixed(2) + '%' : def.signed ? fmtSigned(v) : v.toFixed(1));
    if (po && playoffs) {                      // playoff seasons, one point per postseason
      const k = PLAYOFF_KEYS[def.key as string];
      const rows = playoffs.seasons;
      return {
        type: 'line',
        data: { labels: rows.map(r => r.season), datasets: [{ label: `${def.label} (playoffs)`, data: rows.map(r => { const v = r[k] as number | null; return v == null ? null : def.pct ? v * 100 : v; }),
          borderColor: PALETTE.blue, backgroundColor: PALETTE.blueDim, tension: 0.3, pointRadius: rows.map(r => (r.result === 'Champion' ? 6 : 3)),
          pointBackgroundColor: rows.map(r => (r.result === 'Champion' ? PALETTE.amber : PALETTE.blue)), pointHoverRadius: 6, borderWidth: 2.5, fill: true } as never] },
        options: baseOptions({
          plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: {
            label: (c: { parsed: { y: number } }) => `${def.label}: ${fmt(c.parsed.y)}`,
            afterTitle: (items: { dataIndex: number }[]) => { const r = rows[items[0].dataIndex]; return `${r.team_name ?? r.team} \u00b7 ${r.result ?? ''} \u00b7 ${r.g} games`; },
          } } },
          scales: { x: axis(), y: axis({ ticks: { callback: (v: number) => (def.pct ? v.toFixed(2) + '%' : v) } }) },
        }),
      };
    }
    const scale = (v: number | null | undefined) => (v == null ? null : def.pct ? v * 100 : v);
    const actual = seasons.map(s => scale(s[def.key] as number | null));
    // projection: continue from the last real season with a dashed line and a shaded 60% range
    const key = def.key as string;
    const future = projection?.projected && PROJECTABLE.has(key)
      ? projection.horizons.filter(h => (h as unknown as Record<string, number | null>)[key] != null) : [];
    const last = seasons[seasons.length - 1];
    const showProj = future.length > 0 && last?.season === projection?.base_season;
    const labels = [...seasons.map(s => s.season), ...(showProj ? future.map(h => h.season) : [])];
    const pad = (n: number) => Array<null>(n).fill(null);
    const fv = (h: (typeof future)[number], suffix: string) => scale((h as unknown as Record<string, number | null>)[key + suffix]);
    const datasets: ChartConfiguration['data']['datasets'] = [{
      label: def.label, data: [...actual, ...pad(showProj ? future.length : 0)],
      borderColor: PALETTE.amber, backgroundColor: PALETTE.amberDim, tension: 0.3, pointRadius: 3,
      pointBackgroundColor: PALETTE.amber, pointHoverRadius: 6, borderWidth: 2.5, fill: true } as never];
    if (showProj) {
      const lastVal = actual[actual.length - 1];
      const n = seasons.length - 1;
      const hasBand = future.every(h => fv(h, '_lo') != null);
      if (hasBand) {
        datasets.push({ label: 'Projection range (low)', data: [...pad(n), lastVal, ...future.map(h => fv(h, '_lo'))],
                        borderColor: 'transparent', pointRadius: 0, fill: false, tension: 0.3 } as never);
        datasets.push({ label: 'Projection range', data: [...pad(n), lastVal, ...future.map(h => fv(h, '_hi'))],
                        borderColor: 'transparent', backgroundColor: 'rgba(74,143,184,0.18)', pointRadius: 0, fill: '-1', tension: 0.3 } as never);
      }
      datasets.push({ label: 'Projection', data: [...pad(n), lastVal, ...future.map(h => fv(h, ''))], borderColor: PALETTE.blue,
                      borderDash: [6, 4], pointRadius: [...pad(n + 1).map(() => 0), ...future.map(() => 3)], pointBackgroundColor: PALETTE.blue,
                      borderWidth: 2, fill: false, tension: 0.3 } as never);
    }
    return {
      type: 'line',
      data: { labels, datasets },
      options: baseOptions({
        plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, filter: (c: { parsed: { y: number | null } }) => c.parsed.y != null, callbacks: {
          label: (c: { parsed: { y: number }; dataset: { label?: string } }) =>
            c.dataset.label === 'Projection range (low)' ? `Range from ${fmt(c.parsed.y)}`
              : c.dataset.label === 'Projection range' ? `Range to ${fmt(c.parsed.y)}` : `${c.dataset.label === 'Projection' ? 'Projected' : def.label}: ${fmt(c.parsed.y)}`,
          afterTitle: (items: { dataIndex: number }[]) => {
            const s = seasons[items[0].dataIndex];
            return s ? `${s.team || ''}${s.age ? ' \u00b7 age ' + s.age : ''}` : 'Projection';
          },
        } } },
        scales: { x: axis(), y: axis({ ticks: { callback: (v: number) => (def.pct ? v.toFixed(2) + '%' : v) } }) },
      }),
    };
  }, [seasons, def, projection, po, playoffs]);
  return (
    <>
      {hasPlayoffs && <Pills options={[{ value: 'regular', label: 'Regular season' }, { value: 'playoffs', label: 'Playoffs' }]} value={po ? 'playoffs' : 'regular'} onChange={v => setType(v)} id="pc-season-type" />}
      <Pills options={available.map(s => ({ value: s.key as string, label: s.label }))} value={stat} onChange={v => setStat(v)} id="pc-stat-pills" />
      <ChartCanvas config={config} testId="player-chart" />
    </>
  );
}

// ---- Advanced metrics ----------------------------------------------------------
export function AdvancedPanel({ player, seasons }: { player: PlayerDetail; seasons: PlayerSeason[] }) {
  if (!seasons.some(s => s.per != null || s.ws != null)) return null;
  const best = (key: keyof PlayerSeason) => seasons.filter(s => s[key] != null && (s.g || 0) >= 20)
    .reduce<PlayerSeason | null>((b, s) => (!b || (s[key] as number) > (b[key] as number) ? s : b), null);
  const peak = (key: keyof PlayerSeason, fmt: StatFormat, l: string) => {
    const s = best(key);
    return { l, v: s ? formatStat(fmt, s[key] as number) : '\u2014', sub: s ? String(s.season) : '' };
  };
  const cells = [
    { l: 'Career WS', v: fmtNum(player.ws), sub: '' }, { l: 'Career VORP', v: fmtNum(player.vorp), sub: '' },
    peak('per', 'num', 'Best PER'), peak('ws_48', 'num3', 'Best WS/48'), peak('bpm', 'signed', 'Best BPM'), peak('ts_pct', 'pct', 'Best TS%'),
  ];
  return (
    <Panel id="pc-advanced-panel">
      <SectionHead title="Advanced Metrics" small>Career value and peak seasons. Win Shares and PER go back to the 1950s; BPM and VORP start in 1973-74.</SectionHead>
      <div className="player-stat-row" id="pc-advanced-stats">
        {cells.map(c => <div className="ps-cell" key={c.l}><div className="v">{c.v}</div><div className="l">{c.l}{c.sub && ` \u00b7 ${c.sub}`}</div></div>)}
      </div>
    </Panel>
  );
}

// ---- Similar players ------------------------------------------------------------
// signed whole number without a "-0"
const signedInt = (n: number) => { const r = Math.round(n); return `${r > 0 ? '+' : ''}${r === 0 ? 0 : r}`; };

const FINGERPRINT: { key: string; label: string; fmt: (v: number) => string }[] = [
  { key: 'pts_idx', label: 'Scoring', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'trb_idx', label: 'Rebounding', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'ast_idx', label: 'Playmaking', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'stl_idx', label: 'Steals', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'blk_idx', label: 'Blocks', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'ts_idx', label: 'Efficiency (TS+)', fmt: v => `${Math.round(v * 100)}` },
  { key: 'usg_percent', label: 'Usage', fmt: v => `${v.toFixed(1)}%` },
  { key: 'x3p_ar_diff', label: '3PT tendency', fmt: v => `${signedInt(v * 100)} pts vs lg` },
  { key: 'x3p_pos_diff', label: '3PT vs. his size', fmt: v => `${signedInt(v * 100)} pts vs peers` },
  { key: 'x3p_accuracy', label: '3PT accuracy', fmt: v => `${v > 0 ? '+' : ''}${v.toFixed(2)} makes/36 vs avg` },
  { key: 'ft_rate_diff', label: 'Gets to the line', fmt: v => `${signedInt(v * 100)} FTA per 100 FGA vs lg` },
  { key: 'assisted_diff', label: 'Assisted shots', fmt: v => `${signedInt(v * 100)} pts vs lg` },
  { key: 'rim_diff', label: 'Shots at the rim', fmt: v => `${signedInt(v * 100)} pts vs lg` },
  { key: 'mid_diff', label: 'Mid-range shots', fmt: v => `${signedInt(v * 100)} pts vs lg` },
];

export function SimilarPanel({ playerId }: { playerId: string }) {
  const navigate = useNavigate();
  const [eraRaw, setEra] = useQueryParam('era', 'all');
  const era = oneOf(eraRaw, ['all', 'same'] as const, 'all');
  const { data, error } = useApi<SimilarResponse>(`/players/${playerId}/similar?era=${era}&limit=8`);
  return (
    <Panel id="pc-similar-panel">
      <SectionHead title="Similar Players" small>
        Matched on three things, all relative to each player&rsquo;s league so eras can mix: a career stat fingerprint (scoring, rebounding, playmaking and defensive rates, efficiency, usage, three-point volume against the league and against players his size, height); how he scores (free throws per shot, three-point accuracy, and from 1996-97 on, how many of his shots were assisted and where they came from); and his mix of playing styles, so players who changed roles match others who made the same change. Stats an older player never had recorded count as a partial mismatch. Scores run 0&ndash;100; unique players have lower top scores because nobody plays quite like them.
      </SectionHead>
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      {data && !data.fingerprint && <NoData>Not enough tracked minutes for a reliable match (needs 3,000+ career minutes; minutes were first recorded in 1951-52).</NoData>}
      {data?.fingerprint && (
        <>
          <div className="similar-fingerprint">
            {FINGERPRINT.map(f => {
              const v = data.fingerprint![f.key];
              return v == null ? null : <div className="fp-cell" key={f.key}><div className="v">{f.fmt(v)}</div><div className="l">{f.label}</div></div>;
            })}
          </div>
          <Pills options={[{ value: 'all', label: 'Any era' }, { value: 'same', label: 'Same era' }]} value={era} onChange={v => setEra(v)} id="pc-similar-era" />
          <div id="pc-similar-list">
            {data.matches.length === 0 && <NoData>No close matches whose careers overlapped this era. Try &ldquo;Any era&rdquo;.</NoData>}
            {data.matches.map(p => (
              <div className="similar-row" key={p.player_id}>
                <div className="similar-score"><div className="similar-score-fill" style={{ width: `${p.score}%` }} /><span>{p.score}</span></div>
                <div className="similar-name">
                  <Link className="name-link" to={`/players/${p.player_id}`}>{p.player}</Link>{p.hof && <HofBadge />}
                  <div className="similar-meta">{p.pos || '\u2014'} &middot; {p.first_season}&ndash;{p.last_season} &middot; {fmtNum(p.ppg)} / {fmtNum(p.rpg)} / {fmtNum(p.apg)}</div>
                  {p.styles && p.styles.length > 0 && (
                    <div className="similar-styles">{p.styles.map(st => (
                      <span key={st.key} style={{ color: roleColor(st.key) }}>{st.name} {st.share}%</span>))}</div>
                  )}
                </div>
                <button className="pill-btn similar-compare" type="button" onClick={() => navigate(`/compare/players/${playerId}/${p.player_id}`)}>Compare &rarr;</button>
              </div>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}

// ---- Awards timeline --------------------------------------------------------------
export const AWARD_LABELS: Record<string, string> = {
  'nba mvp': 'MVP', 'nba dpoy': 'Defensive Player of the Year', 'nba mip': 'Most Improved Player',
  'nba roy': 'Rookie of the Year', 'nba smoy': 'Sixth Man of the Year', 'nba clutch_poy': 'Clutch Player of the Year',
  'aba mvp': 'ABA MVP', 'aba roy': 'ABA Rookie of the Year', 'baa roy': 'BAA Rookie of the Year',
};
export const AWARD_SHORT: Record<string, string> = {
  'nba mvp': 'MVP', 'nba dpoy': 'DPOY', 'nba mip': 'MIP', 'nba roy': 'ROY', 'nba smoy': '6MOY',
  'nba clutch_poy': 'Clutch POY', 'aba mvp': 'ABA MVP', 'aba roy': 'ABA ROY', 'baa roy': 'BAA ROY',
};
export function teamLabel(type: string, number: string) {
  if (type === 'All-NBA') return `All-NBA ${number} Team`;
  if (type === 'All-Defense') return `All-Defensive ${number} Team`;
  if (type === 'All-Rookie') return `All-Rookie ${number} Team`;
  return `${type} ${number}`;
}

export function AwardsTimeline({ playerId }: { playerId: string }) {
  const { data, error } = useApi<PlayerHonors>(`/players/${playerId}/honors`);
  const seasons = useMemo(() => {
    if (!data) return [];
    const m = new Map<number, { pills: { text: string; won: boolean; star?: boolean; trophy?: boolean }[] }>();
    const at = (s: number) => { if (!m.has(s)) m.set(s, { pills: [] }); return m.get(s)!.pills; };
    // order within a season: awards won, All-Star, All-NBA/Defense teams, voting finishes
    const won = data.awards.filter(a => a.winner), votes = data.awards.filter(a => !a.winner && (a.share || 0) > 0.05);
    won.forEach(a => at(a.season).push({ text: AWARD_LABELS[a.award] || a.award, won: true, trophy: true }));
    (data.title_seasons ?? []).forEach(s => at(s).push({ text: 'NBA Champion', won: true, trophy: true }));
    (data.finals_mvp_seasons ?? []).forEach(s => at(s).push({ text: 'Finals MVP', won: true, trophy: true }));
    data.all_star_seasons.forEach(s => at(s).push({ text: '\u2605 All-Star', won: true, star: true }));
    data.all_league_teams.forEach(e => at(e.season).push({ text: teamLabel(e.team_type, e.team_number), won: true }));
    votes.forEach(a => at(a.season).push({ text: `${AWARD_SHORT[a.award] || a.award} voting (${Math.round((a.share || 0) * 100)}% share)`, won: false }));
    return [...m.entries()].sort((a, b) => b[0] - a[0]);
  }, [data]);
  if (data && seasons.length === 0) return null;
  return (
    <Panel id="pc-awards-panel">
      <SectionHead title="Awards & Honors" small />
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      <div id="pc-awards-timeline">
        {seasons.map(([season, { pills }]) => (
          <div className="awards-timeline-row" key={season}>
            <span className="awards-season-tag">{season}</span>
            <div>{pills.map((p, i) => (
              <span key={i} className={`award-pill ${p.won ? 'won' : ''} ${p.star ? 'allstar-pill' : ''}`}>
                {p.trophy && <span className="award-trophy">{'\u{1F3C6}'}</span>}{p.text}
              </span>
            ))}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---- On-court role -----------------------------------------------------------------
const POSITIONS = [['pg_pct', 'PG'], ['sg_pct', 'SG'], ['sf_pct', 'SF'], ['pf_pct', 'PF'], ['c_pct', 'C']] as const;

export function RolePanel({ playerId }: { playerId: string }) {
  const { data: seasons, error } = useApi<PbpSeason[]>(`/players/${playerId}/play-by-play`);
  const latest = seasons?.[seasons.length - 1];
  const tone = (v: number | null) => (v == null ? '' : v > 0 ? 'positive' : v < 0 ? 'negative' : '');
  return (
    <Panel id="pc-pbp-panel">
      <SectionHead title="On-Court Role" small>
        {seasons && seasons.length === 0
          ? 'Play-by-play tracking begins in the 1996/97 season \u2014 not available for this player\u2019s career.'
          : 'Career-average position mix and per-season playmaking/discipline stats (1996/97 onward).'}
      </SectionHead>
      {error && <ErrorNote error={error} />}
      {!seasons && !error && <Loading />}
      {seasons && seasons.length === 0 && <NoData>No data.</NoData>}
      {latest && (
        <div className="panel-row">
          <div>
            <div className="pbp-subhead">Time by position</div>
            <div id="pc-position-bars">
              {POSITIONS.map(([key, label]) => {
                const vals = seasons!.map(s => s[key]).filter((v): v is number => v != null);
                const pct = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;   // stored as 0-100
                return (
                  <div className="position-bar-row" key={key}>
                    <span className="position-bar-label">{label}</span>
                    <div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${pct}%` }} /></div>
                    <span className="position-bar-pct">{pct.toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <div className="pbp-subhead">Playmaking &amp; discipline</div>
            <div className="pbp-stat-grid" id="pc-pbp-stats">
              {[
                { l: 'On-court +/- per 100', v: fmtSigned(latest.on_court_plus_minus), cls: tone(latest.on_court_plus_minus) },
                { l: 'Net rating swing', v: fmtSigned(latest.net_plus_minus), cls: tone(latest.net_plus_minus) },
                { l: 'Pts generated by assists', v: fmtInt(latest.pts_generated_by_ast) },
                { l: 'And-1s', v: fmtInt(latest.and1) },
                { l: 'Shooting fouls drawn', v: fmtInt(latest.shooting_foul_drawn) },
                { l: 'Shooting fouls committed', v: fmtInt(latest.shooting_foul_committed) },
                { l: 'Bad-pass turnovers', v: fmtInt(latest.bad_pass_to) },
                { l: 'FGA blocked', v: fmtInt(latest.fga_blocked) },
              ].map(c => <div className="pbp-stat-cell" key={c.l}><div className={`v ${c.cls || ''}`}>{c.v}</div><div className="l">{c.l}</div></div>)}
            </div>
            <div style={{ marginTop: 10, fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--chalk-dim)' }}>Showing {latest.season} season</div>
          </div>
        </div>
      )}
    </Panel>
  );
}
