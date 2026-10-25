import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { Archetype, ArchetypeModel, ArchetypePlayers } from '../../api/types';
import { ErrorNote, HofBadge, Loading, Panel, Pills, SectionHead } from '../../components/ui';
import { fmtNum } from '../../lib/format';
import { useQueryParam } from '../../lib/useQuery';
import { roleColor } from './archetypeColors';
import { areaPath, arcPath, decadeTicks, linePath, nearestIndex, peakOf, pieSlices, polar, seasonLabel, sharedMax, sparkPoints, yTicks } from './archetypeTrend';

const pct = (v: number | undefined) => `${Math.round((v ?? 0) * 100)}%`;

export function ArchetypesPage() {
  const { data, error } = useApi<ArchetypeModel>('/models/archetypes');
  const [selected, setSelected] = useQueryParam('role', '');
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const role = data.archetypes.find(a => a.key === selected);
  const pick = (key: string) => setSelected(key === selected ? '' : key);
  return (
    <div id="archetypes-page">
      <TrendSection model={data} selected={selected} onSelect={pick} />
      <div className="archetype-grid" id="archetype-grid">
        {[...data.archetypes].sort((a, b) => (b.share_by_decade['2020'] ?? 0) - (a.share_by_decade['2020'] ?? 0)).map(a => (
          <ArchetypeCard key={a.key} a={a} labels={data.method.feature_labels} active={a.key === selected}
                         onOpen={() => setSelected(a.key === selected ? '' : a.key)} />
        ))}
      </div>
      {role && <RolePlayers key={role.key} role={role} />}
      <details className="lineup-notes" open={false}>
        <summary>How it works</summary>
        <p>Every player-season with at least {data.method.min_minutes.toLocaleString()} minutes since {data.method.first_season} (minutes weren&rsquo;t recorded earlier) is described by its style relative to that season&rsquo;s league: per-36 scoring, rebounding, playmaking, steal and block rates, true shooting, usage, how often he shoots threes (against the whole league and against players his height that season), and height. Most seasons blend roles, so each one gets a share of every role based on how close it is to each role&rsquo;s center; a player&rsquo;s career style is the minutes-weighted blend of his seasons. K-means clustering, weighted by minutes, finds the {data.method.k} core roles from {data.method.train_from - 1}-{String(data.method.train_from).slice(2)} on, when every stat exists; each cluster is named by the role profile it most resembles, so names hold up when the model is retrained on new data.</p>
        <p>Older seasons are placed in the nearest role using the stats they have: there was no three-point line before 1979-80 and no blocks, steals or usage before the mid-1970s, so early-era roles lean on scoring, rebounding, playmaking and height. Stretch bigs are under 1% of minutes, too few for clustering to separate, so they&rsquo;re defined by a rule: a PF or C, 6&rsquo;9&rdquo;+, who shoots threes far more than players his size. Roles are a description of style, not quality.</p>
      </details>
    </div>
  );
}

type TrendView = 'each' | 'year';
const VIEWS: { value: TrendView; label: string }[] = [{ value: 'each', label: 'Each role' }, { value: 'year', label: 'By year' }];
// roles in a fixed order (traditional bigs first, then perimeter roles) so a slice stays in place as the years change
const PIE_ORDER = ['rim-protector', 'rebounding-forward', 'scoring-big', 'stretch-big', 'role-player', 'scoring-wing',
                   'spot-up-shooter', 'combo-guard', 'floor-general', 'star-creator'];

function useWidth(ref: RefObject<HTMLElement | null>) {
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

function TrendSection({ model, selected, onSelect }: { model: ArchetypeModel; selected: string; onSelect: (key: string) => void }) {
  const [viewParam, setView] = useQueryParam('view', 'each');
  const view: TrendView = viewParam === 'year' ? 'year' : 'each';
  const role = model.archetypes.find(a => a.key === selected);
  const seasons = model.trend.seasons;
  const max = useMemo(() => sharedMax(Object.values(model.trend.shares).map(v => v.map(x => x * 100))), [model]);
  const ordered = useMemo(() => [...model.archetypes].sort((a, b) => (b.share_by_decade['2020'] ?? 0) - (a.share_by_decade['2020'] ?? 0)), [model]);
  return (
    <Panel id="archetype-trend">
      <SectionHead title="How the league's roles changed" small>
        Share of all minutes (players with {model.method.min_minutes.toLocaleString()}+ minutes) by role, each season. Before 1979-80 there were no threes, and before the mid-1970s no blocks, steals or usage, so early roles rest on fewer stats.
      </SectionHead>
      <Pills options={VIEWS} value={view} onChange={setView} id="archetype-view" />
      {view === 'each' ? (
        <>
          {role && <RoleDetail key={role.key} role={role} seasons={seasons} values={model.trend.shares[String(role.id)].map(v => v * 100)} onClose={() => onSelect(role.key)} />}
          <div className="archetype-minis" data-testid="archetype-chart">
            {ordered.map(a => (
              <MiniTrend key={a.key} role={a} seasons={seasons} values={model.trend.shares[String(a.id)].map(v => v * 100)} max={max}
                         active={a.key === selected} dimmed={!!selected && a.key !== selected} onSelect={() => onSelect(a.key)} />
            ))}
          </div>
        </>
      ) : (
        <YearPie model={model} selected={selected} onSelect={onSelect} />
      )}
      <div className="similar-meta archetype-trend-note">
        {view === 'each' && <span>The small charts share one scale (0 to {max}% of minutes), so heights compare across roles.</span>}
        {role
          ? <span>Showing <b>{role.name}</b>. <button type="button" className="pill-btn" onClick={() => document.getElementById('role-players')?.scrollIntoView({ behavior: 'smooth' })}>See its players &darr;</button></span>
          : <span>Click a role to enlarge it and list its players.</span>}
      </div>
    </Panel>
  );
}

/** One role's share of league minutes over time, drawn as a line on the scale shared by every role. */
function MiniTrend({ role, seasons, values, max, active, dimmed, onSelect }: {
  role: Archetype; seasons: number[]; values: number[]; max: number; active: boolean; dimmed: boolean; onSelect: () => void;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 300;
  const H = 84;
  const pts = useMemo(() => sparkPoints(values, W, H, max), [values, max]);
  const peak = useMemo(() => peakOf(seasons, values), [seasons, values]);
  const i = hover ?? values.length - 1;
  const color = roleColor(role.key);
  const then = role.share_by_decade['1980'];
  const now = role.share_by_decade['2020'];
  return (
    <button type="button" className={`archetype-mini ${active ? 'active' : ''} ${dimmed ? 'dimmed' : ''}`} data-role={role.key} aria-pressed={active}
            style={{ borderTopColor: color }} onClick={onSelect}>
      <div className="archetype-head">
        <span className="archetype-dot" style={{ background: color }} />
        <span className="archetype-name">{role.name}</span>
        <span className="mini-value">{values[i].toFixed(1)}%<small> {seasons[i]}</small></span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="mini-svg" role="img"
           aria-label={`${role.name}: ${values[0].toFixed(0)}% of minutes in ${seasons[0]}, ${values[values.length - 1].toFixed(0)}% in ${seasons[seasons.length - 1]}`}
           onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHover(nearestIndex(e.clientX - r.left, r.width, values.length)); }}
           onMouseLeave={() => setHover(null)}>
        <line x1="0" x2={W} y1={H} y2={H} className="mini-base" />
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="mini-grid" />
        <path d={areaPath(pts, H)} fill={color} opacity="0.18" />
        <path d={linePath(pts)} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
        {hover !== null && <line x1={pts[hover][0]} x2={pts[hover][0]} y1="0" y2={H} className="mini-cursor" />}
      </svg>
      <div className="mini-axis"><span>{seasons[0]}</span><span>{seasons[seasons.length - 1]}</span></div>
      <div className="similar-meta">
        {peak && <div>Peak <b>{peak.value.toFixed(0)}%</b> in {peak.season}</div>}
        <div>1980s {pct(then)} &rarr; 2020s {pct(now)}</div>
      </div>
    </button>
  );
}

/** The picked role, enlarged: full-width chart with axes, decade gridlines, hover read-out and the role's description. */
function RoleDetail({ role, seasons, values, onClose }: { role: Archetype; seasons: number[]; values: number[]; onClose: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box);
  const [hover, setHover] = useState<number | null>(null);
  const H = 320;
  const m = { l: 46, r: 16, t: 18, b: 30 };
  const max = sharedMax([values]);
  const innerW = Math.max(10, width - m.l - m.r);
  const innerH = H - m.t - m.b;
  const pts = useMemo(() => sparkPoints(values, innerW, innerH, max), [values, innerW, innerH, max]);
  const peak = peakOf(seasons, values);
  const peakIdx = peak ? seasons.indexOf(peak.season) : -1;
  const color = roleColor(role.key);
  const i = hover ?? values.length - 1;
  const x = (idx: number) => m.l + pts[idx][0];
  const y = (idx: number) => m.t + pts[idx][1];
  return (
    <div className="archetype-detail" data-testid="archetype-detail" style={{ borderTopColor: color }}>
      <div className="archetype-detail-head">
        <span className="archetype-dot" style={{ background: color }} />
        <span className="archetype-detail-name">{role.name}</span>
        <button type="button" className="pill-btn" onClick={onClose} aria-label={`Close the ${role.name} chart`}>Close &times;</button>
      </div>
      <p className="archetype-desc">{role.description}</p>
      <div className="archetype-detail-stats">
        <span><b>{values[i].toFixed(1)}%</b> of minutes in {seasonLabel(seasons[i])}</span>
        {peak && <span>Peak <b>{peak.value.toFixed(1)}%</b> in {seasonLabel(peak.season)}</span>}
        <span>1980s <b>{pct(role.share_by_decade['1980'])}</b> &rarr; 2020s <b>{pct(role.share_by_decade['2020'])}</b></span>
      </div>
      <div ref={box} className="archetype-detail-chart">
        {width > 0 && (
          <svg width={width} height={H} role="img" aria-label={`${role.name}: share of league minutes by season`}
               onMouseMove={e => { const r = e.currentTarget.getBoundingClientRect(); setHover(nearestIndex(e.clientX - r.left - m.l, innerW, values.length)); }}
               onMouseLeave={() => setHover(null)}>
            {yTicks(max).map(t => (
              <g key={t}>
                <line x1={m.l} x2={width - m.r} y1={m.t + innerH - (t / max) * innerH} y2={m.t + innerH - (t / max) * innerH} className={t === 0 ? 'mini-base' : 'mini-grid'} />
                <text x={m.l - 8} y={m.t + innerH - (t / max) * innerH + 4} textAnchor="end" className="detail-tick">{t}%</text>
              </g>
            ))}
            {decadeTicks(seasons).map(s => {
              const idx = seasons.indexOf(s);
              return <text key={s} x={x(idx)} y={H - 8} textAnchor="middle" className="detail-tick">{s}</text>;
            })}
            <g transform={`translate(${m.l},${m.t})`}>
              <path d={areaPath(pts, innerH)} fill={color} opacity="0.22" />
              <path d={linePath(pts)} fill="none" stroke={color} strokeWidth="2.5" />
            </g>
            {peakIdx >= 0 && hover === null && (
              <g>
                <circle cx={x(peakIdx)} cy={y(peakIdx)} r="5" fill={color} stroke="#1c1612" strokeWidth="2" />
                <text x={Math.min(Math.max(x(peakIdx), m.l + 40), width - m.r - 40)} y={Math.max(y(peakIdx) - 10, 12)} textAnchor="middle" className="detail-label">Peak {peak!.value.toFixed(1)}%</text>
              </g>
            )}
            {hover !== null && (
              <g>
                <line x1={x(hover)} x2={x(hover)} y1={m.t} y2={m.t + innerH} className="mini-cursor" />
                <circle cx={x(hover)} cy={y(hover)} r="5" fill={color} stroke="#1c1612" strokeWidth="2" />
                <text x={Math.min(Math.max(x(hover), m.l + 52), width - m.r - 52)} y={Math.max(y(hover) - 12, 12)} textAnchor="middle" className="detail-label">
                  {seasonLabel(seasons[hover])}: {values[hover].toFixed(1)}%
                </text>
              </g>
            )}
          </svg>
        )}
      </div>
    </div>
  );
}

/** A pie of every role's share of league minutes in one season, with a slider (and play button) to move through the years. */
function YearPie({ model, selected, onSelect }: { model: ArchetypeModel; selected: string; onSelect: (key: string) => void }) {
  const seasons = model.trend.seasons;
  const [idx, setIdx] = useState(seasons.length - 1);
  const [playing, setPlaying] = useState(false);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setIdx(i => {
      if (i >= seasons.length - 1) { setPlaying(false); return i; }
      return i + 1;
    }), 220);
    return () => clearInterval(t);
  }, [playing, seasons.length]);
  const roles = useMemo(() => [...model.archetypes].sort((a, b) => PIE_ORDER.indexOf(a.key) - PIE_ORDER.indexOf(b.key)), [model]);
  const values = roles.map(a => model.trend.shares[String(a.id)][idx] * 100);
  const slices = pieSlices(values);
  const focus = hoverKey ?? selected;
  const C = 190;
  const R1 = 180;
  const R0 = 104;
  const rows = roles.map((a, k) => ({ a, v: values[k], s: slices[k] })).sort((p, q) => q.v - p.v);
  const top = rows[0]?.v || 1;
  return (
    <div className="year-pie" data-testid="archetype-chart">
      <div className="year-pie-body">
        <svg viewBox={`0 0 ${C * 2} ${C * 2}`} className="year-pie-svg" role="img" aria-label={`Share of league minutes by role in ${seasonLabel(seasons[idx])}`}>
          {roles.map((a, k) => {
            const s = slices[k];
            const dim = !!focus && focus !== a.key;
            const [lx, ly] = polar(C, C, (R0 + R1) / 2, s.mid);
            return (
              <g key={a.key} className="pie-slice" data-role={a.key} opacity={dim ? 0.3 : 1} onClick={() => onSelect(a.key)}
                 onMouseEnter={() => setHoverKey(a.key)} onMouseLeave={() => setHoverKey(null)} style={{ cursor: 'pointer' }}>
                <path d={arcPath(C, C, R0, R1, s.start, s.end)} fill={roleColor(a.key)} stroke="#1c1612" strokeWidth="2" />
                {s.fraction >= 0.05 && <text x={lx} y={ly + 4} textAnchor="middle" className="pie-label">{Math.round(values[k])}%</text>}
              </g>
            );
          })}
          <text x={C} y={C - 4} textAnchor="middle" className="pie-season">{seasonLabel(seasons[idx])}</text>
          <text x={C} y={C + 22} textAnchor="middle" className="pie-sub">share of league minutes</text>
        </svg>
        <ul className="year-pie-legend">
          {rows.map(({ a, v }) => (
            <li key={a.key}>
              <button type="button" className={`year-row ${selected === a.key ? 'active' : ''} ${focus && focus !== a.key ? 'dimmed' : ''}`} data-role={a.key}
                      onClick={() => onSelect(a.key)} onMouseEnter={() => setHoverKey(a.key)} onMouseLeave={() => setHoverKey(null)}>
                <span className="archetype-dot" style={{ background: roleColor(a.key) }} />
                <span className="year-row-name">{a.name}</span>
                <span className="year-row-bar"><span style={{ width: `${(v / top) * 100}%`, background: roleColor(a.key) }} /></span>
                <span className="year-row-val">{v.toFixed(1)}%</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="year-controls">
        <button type="button" className="pill-btn" id="year-play" onClick={() => { if (idx >= seasons.length - 1) setIdx(0); setPlaying(p => !p); }}>
          {playing ? 'Pause' : 'Play'}
        </button>
        <span className="year-end">{seasons[0]}</span>
        <input type="range" min={0} max={seasons.length - 1} value={idx} data-testid="year-slider" aria-label="Season"
               onChange={e => { setPlaying(false); setIdx(Number(e.target.value)); }} />
        <span className="year-end">{seasons[seasons.length - 1]}</span>
      </div>
    </div>
  );
}

function ArchetypeCard({ a, labels, active, onOpen }: { a: Archetype; labels: Record<string, string>; active: boolean; onOpen: () => void }) {
  const top = Object.entries(a.profile).sort((x, y) => Math.abs(y[1]) - Math.abs(x[1])).slice(0, 4);
  const then = a.share_by_decade['1980'], now = a.share_by_decade['2020'];
  return (
    <div className={`archetype-card ${active ? 'active' : ''}`} style={{ borderTopColor: roleColor(a.key) }} data-role={a.key}>
      <div className="archetype-head">
        <span className="archetype-dot" style={{ background: roleColor(a.key) }} />
        <span className="archetype-name">{a.name}</span>
        {a.rule_based && <span className="hof-badge" title="Defined by a rule, not clustering">rule</span>}
      </div>
      <p className="archetype-desc">{a.description}</p>
      <div className="archetype-profile">
        {top.map(([f, v]) => (
          <div className="archetype-trait" key={f}>
            <span>{labels[f] ?? f}</span>
            <div className="trait-track"><div className={`trait-fill ${v < 0 ? 'neg' : ''}`} style={{ width: `${Math.min(50, Math.abs(v) * 20)}%` }} /></div>
            <span className="trait-val">{v > 0 ? '+' : ''}{v.toFixed(1)}</span>
          </div>
        ))}
      </div>
      <div className="archetype-share">1980s <b>{pct(then)}</b> &rarr; 2020s <b>{pct(now)}</b> of minutes</div>
      <div className="archetype-examples">
        {a.examples.slice(0, 4).map(e => <Link key={e.player_id} to={`/players/${e.player_id}`} className="pill-btn">{e.player} &rsquo;{String(e.season).slice(2)}</Link>)}
      </div>
      {a.classic_examples.length > 0 && (
        <div className="similar-meta" style={{ marginTop: 6 }}>
          Earlier: {a.classic_examples.slice(0, 3).map((e, i) => <span key={e.player_id}>{i > 0 && ', '}<Link to={`/players/${e.player_id}`} className="name-link">{e.player}</Link> {e.season}</span>)}
        </div>
      )}
      <button type="button" className="pill-btn archetype-more" onClick={onOpen}>{active ? 'Hide players' : 'See players \u2192'}</button>
    </div>
  );
}

const DECADES = ['all', '1950', '1960', '1970', '1980', '1990', '2000', '2010', '2020'] as const;

function RolePlayers({ role }: { role: Archetype }) {
  const [decade, setDecade] = useQueryParam('decade', 'all');
  const { data, error } = useApi<ArchetypePlayers>(`/models/archetypes/${role.key}?limit=25${decade !== 'all' ? `&decade=${decade}` : ''}`);
  return (
    <Panel id="role-players">
      <SectionHead title={`${role.name}: most minutes`} small>{role.description}</SectionHead>
      <Pills options={DECADES.map(d => ({ value: d, label: d === 'all' ? 'All eras' : `${d}s` }))} value={decade} onChange={setDecade} />
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      {data && data.players.length === 0 && <div className="no-data-note">No {role.name.toLowerCase()} seasons in the {decade}s.</div>}
      {data && data.players.length > 0 && (
        <div className="table-scroll">
          <table className="lb-table">
            <thead><tr><th>Player</th><th>Season</th><th>Team</th><th>PTS</th><th>REB</th><th>AST</th><th>MIN</th><th>Share</th><th>Next style</th></tr></thead>
            <tbody>
              {data.players.map(p => (
                <tr key={p.player_id + p.season}>
                  <td className="name-cell"><Link to={`/players/${p.player_id}`}>{p.player}</Link>{p.hof && <HofBadge />}</td>
                  <td>{p.season}</td><td>{p.team}</td><td>{fmtNum(p.pts)}</td><td>{fmtNum(p.trb)}</td><td>{fmtNum(p.ast)}</td><td>{fmtNum(p.mp)}</td>
                  <td title="Share of this season's style that fits this role">{p.fit}%</td><td className="similar-meta">{p.secondary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
