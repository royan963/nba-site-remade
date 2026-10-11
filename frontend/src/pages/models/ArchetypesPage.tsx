import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../../api/hooks';
import type { Archetype, ArchetypeModel, ArchetypePlayers } from '../../api/types';
import { ChartCanvas, ErrorNote, HofBadge, Loading, Panel, Pills, SectionHead } from '../../components/ui';
import { MONO, PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { fmtNum } from '../../lib/format';
import { useQueryParam } from '../../lib/useQuery';
import { roleColor } from './archetypeColors';

const pct = (v: number | undefined) => `${Math.round((v ?? 0) * 100)}%`;

export function ArchetypesPage() {
  const { data, error } = useApi<ArchetypeModel>('/models/archetypes');
  const [selected, setSelected] = useQueryParam('role', '');
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const role = data.archetypes.find(a => a.key === selected);
  return (
    <div id="archetypes-page">
      <TrendChart model={data} />
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

function TrendChart({ model }: { model: ArchetypeModel }) {
  const config = useMemo<ChartConfiguration>(() => {
    // stacked from the most "traditional" roles at the bottom to perimeter roles on top
    const order = ['rim-protector', 'rebounding-forward', 'scoring-big', 'stretch-big', 'role-player', 'scoring-wing',
                   'spot-up-shooter', 'combo-guard', 'floor-general', 'star-creator'];
    const roles = [...model.archetypes].sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
    return {
      type: 'line',
      data: {
        labels: model.trend.seasons,
        datasets: roles.map(a => ({
          label: a.name, data: model.trend.shares[String(a.id)].map(v => v * 100),
          borderColor: roleColor(a.key), backgroundColor: roleColor(a.key) + 'cc', fill: true, pointRadius: 0, borderWidth: 1, tension: 0.3,
        })),
      },
      options: baseOptions({
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'bottom', labels: { color: PALETTE.chalkDim, font: MONO, boxWidth: 12, boxHeight: 12 } },
          tooltip: { ...TOOLTIP, itemSort: (x: { parsed: { y: number } }, y: { parsed: { y: number } }) => y.parsed.y - x.parsed.y,
            callbacks: { label: (c: { dataset: { label: string }; parsed: { y: number } }) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } },
        },
        scales: {
          x: axis({ ticks: { maxTicksLimit: 12 } }),
          y: { ...axis({ ticks: { callback: (v: number) => v + '%' } }), stacked: true, min: 0, max: 100,
               title: { display: true, text: 'Share of league minutes', color: PALETTE.chalkDim, font: MONO } },
        },
      }),
    };
  }, [model]);
  return (
    <Panel id="archetype-trend">
      <SectionHead title="How the league's roles changed" small>
        Share of all minutes (players with {model.method.min_minutes.toLocaleString()}+ minutes) by role, each season. Before 1979-80 there were no threes, and before the mid-1970s no blocks, steals or usage, so early roles rest on fewer stats.
      </SectionHead>
      <ChartCanvas config={config} tall testId="archetype-chart" />
    </Panel>
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
