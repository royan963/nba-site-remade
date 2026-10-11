import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { enc } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { TeamHonors, TeamPlayoffs } from '../../api/types';
import { ErrorNote, Loading, NoData, Panel, Pills, SectionHead } from '../../components/ui';
import { fmtInt } from '../../lib/format';
import { oneOf, useQueryParam } from '../../lib/useQuery';
import { AWARD_LABELS, AWARD_SHORT, teamLabel } from '../player/panels';
import { type Franchise } from '../teams/geo';
import { useFranchises } from '../teams/useFranchises';
import { StatBarRow, type StatRowDef } from './StatBars';
import { TeamHeadToHead } from './HeadToHead';
import { SaveComparison } from '../../components/account';

interface Aggregate {
  displayName: string; minSeason: number; maxSeason: number; season?: number; seasons: number;
  w: number; l: number; winPct: number | null; playoffs: number; status: string;
  srs: number | null; o_rtg: number | null; d_rtg: number | null; pace: number | null; pts: number | null;
}

function aggregate(f: Franchise, season?: number): Aggregate | null {
  const rows = season == null ? f.rows : f.rows.filter(r => r.season === season);
  if (!rows.length) return null;
  const sum = (k: 'w' | 'l') => rows.reduce((s, r) => s + (r[k] || 0), 0);
  const avg = (k: 'srs' | 'o_rtg' | 'd_rtg' | 'pace' | 'pts_per_game') => {
    const vals = rows.map(r => r[k]).filter((v): v is number => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  };
  const w = sum('w'), l = sum('l');
  return {
    displayName: season == null ? f.displayName : rows[0].team_name, minSeason: f.minSeason, maxSeason: f.maxSeason, season,
    seasons: rows.length, w, l, winPct: w + l ? w / (w + l) : null, playoffs: rows.filter(r => r.playoffs).length,
    status: rows[rows.length - 1].status, srs: avg('srs'), o_rtg: avg('o_rtg'), d_rtg: avg('d_rtg'), pace: avg('pace'), pts: avg('pts_per_game'),
  };
}

const STAT_DEFS: (StatRowDef & { get: (a: Aggregate) => number | null })[] = [
  { key: 'w', label: 'Wins', fmt: 'int', get: a => a.w },
  { key: 'l', label: 'Losses', fmt: 'int', lowerBetter: true, get: a => a.l },
  { key: 'pct', label: 'Win %', fmt: 'pct', get: a => a.winPct },
  { key: 'srs', label: 'SRS (Strength)', fmt: 'num', get: a => a.srs },
  { key: 'ortg', label: 'Off. Rating', fmt: 'num', get: a => a.o_rtg },
  { key: 'drtg', label: 'Def. Rating', fmt: 'num', lowerBetter: true, get: a => a.d_rtg },
  { key: 'pace', label: 'Pace', fmt: 'num', get: a => a.pace },
  { key: 'pts', label: 'Points/Game', fmt: 'num', get: a => a.pts },
];

export function CompareTeams({ a, b }: { a?: string; b?: string }) {
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const { franchises, bySlug, error } = useFranchises();
  const [scopeRaw, setScope] = useQueryParam('scope', 'career');
  const scope = oneOf(scopeRaw, ['career', 'season'] as const, 'career');
  const fa = a ? bySlug?.get(a) : undefined, fb = b ? bySlug?.get(b) : undefined;
  const { data: poA } = useApi<TeamPlayoffs>(fa ? `/teams/${enc(fa.name)}/playoffs` : null);
  const { data: poB } = useApi<TeamPlayoffs>(fb ? `/teams/${enc(fb.name)}/playoffs` : null);
  const [saRaw, setSa] = useQueryParam('sa', '');
  const [sbRaw, setSb] = useQueryParam('sb', '');
  const pickSeason = (f: Franchise | undefined, raw: string) =>
    f && f.rows.some(r => String(r.season) === raw) ? parseInt(raw, 10) : f?.maxSeason;
  const sa = pickSeason(fa, saRaw), sb = pickSeason(fb, sbRaw);

  if (error) return <ErrorNote error={error} />;
  if (!franchises) return <Loading />;
  const list = [...franchises.values()];
  const go = (na?: string, nb?: string) => {
    const q = search.toString();
    navigate(`/compare/teams${na ? `/${na}` : ''}${na && nb ? `/${nb}` : ''}${q ? `?${q}` : ''}`);
  };
  const select = (value: string | undefined, onChange: (v: string) => void, id: string) => (
    <select id={id} value={value ?? ''} onChange={e => onChange(e.target.value)}>
      <option value="">Select a team&hellip;</option>
      {list.map(f => <option key={f.slug} value={f.slug}>{f.displayName} ({f.minSeason}&ndash;{f.maxSeason})</option>)}
    </select>
  );

  const dataA = fa ? aggregate(fa, scope === 'season' ? sa : undefined) : null;
  const dataB = fb ? aggregate(fb, scope === 'season' ? sb : undefined) : null;

  return (
    <div id="compare-teams">
      <Panel>
        <div className="compare-picker-row">
          {select(a, v => go(v || undefined, b), 'cmp-team-select-a')}
          <div className="compare-vs">VS</div>
          {select(b, v => go(a, v || undefined), 'cmp-team-select-b')}
        </div>
        <div className="compare-team-scope">
          <Pills options={[{ value: 'career', label: 'Full Franchise History' }, { value: 'season', label: 'Specific Season' }]}
                 value={scope} onChange={v => setScope(v)} id="cmp-team-scope-toggle" />
          {scope === 'season' && fa && fb && (
            <div id="cmp-team-season-pickers">
              <select id="cmp-team-season-a" value={sa} onChange={e => setSa(e.target.value)}>
                {[...fa.rows].reverse().map(r => <option key={r.season} value={r.season}>{fa.displayName}: {r.season}</option>)}
              </select>
              <select id="cmp-team-season-b" value={sb} onChange={e => setSb(e.target.value)}>
                {[...fb.rows].reverse().map(r => <option key={r.season} value={r.season}>{fb.displayName}: {r.season}</option>)}
              </select>
            </div>
          )}
        </div>
      </Panel>

      {!(fa && fb) && <div className="empty-state"><div className="big">Pick two teams to compare</div><div>Try the Celtics vs. the Lakers.</div>
        <div style={{ marginTop: 14 }}><button className="pill-btn" type="button" onClick={() => go('boston-celtics', 'los-angeles-lakers')}>Boston Celtics vs Los Angeles Lakers</button></div></div>}

      {fa && fb && dataA && dataB && (
        <div id="cmp-teams-result">
          <div className="cmp-control-row" style={{ marginBottom: 18 }}>
            <SaveComparison kind="teams" a={fa.slug} b={fb.slug}
                            defaultTitle={`${dataA.displayName}${dataA.season ? ` ${dataA.season}` : ''} vs ${dataB.displayName}${dataB.season ? ` ${dataB.season}` : ''}`} />
          </div>
          <div className="panel-row">
            <TeamCard id="cmp-team-card-a" data={dataA} po={poA} />
            <TeamCard id="cmp-team-card-b" data={dataB} po={poB} />
          </div>
          <Panel>
            <SectionHead title="Stat-by-Stat" small />
            <div id="cmp-team-stat-table">
              {STAT_DEFS.map(d => <StatBarRow key={d.key} def={d} a={d.get(dataA)} b={d.get(dataB)} />)}
              {scope === 'career' && poA && poB && PLAYOFF_DEFS.map(d => <StatBarRow key={d.key} def={d} a={d.get(poA)} b={d.get(poB)} />)}
            </div>
          </Panel>
          <TeamHeadToHead a={fa.name} b={fb.name} />
          <Panel>
            <SectionHead title="Accomplishments" small>
              Each team&rsquo;s own record and ratings, and the awards won by players on its roster.
            </SectionHead>
            <div className="cmp-accomplishments-grid" id="cmp-team-accomplishments">
              <Accomplishments franchise={fa} data={dataA} po={poA} />
              <Accomplishments franchise={fb} data={dataB} po={poB} />
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

const PLAYOFF_DEFS: (StatRowDef & { get: (p: TeamPlayoffs) => number | null })[] = [
  { key: 'titles', label: 'Championships', fmt: 'int', get: p => p.titles.length },
  { key: 'finals', label: 'Finals appearances', fmt: 'int', get: p => p.finals_appearances },
  { key: 'pseries', label: 'Playoff series won', fmt: 'int', get: p => p.series_won },
];

function TeamCard({ id, data, po }: { id: string; data: Aggregate; po?: TeamPlayoffs }) {
  const career = data.season == null;
  const thisSeason = !career && po ? po.seasons.find(s => s.season === data.season) : undefined;
  const cells: [string, string | number][] = career
    ? [['Seasons', data.seasons], ['Record', `${fmtInt(data.w)}-${fmtInt(data.l)}`],
       ['Win %', data.winPct != null ? (data.winPct * 100).toFixed(1) + '%' : '\u2014'], ['Playoff Trips', `${data.playoffs} / ${data.seasons}`],
       ['Championships', po ? po.titles.length : '\u2026'], ['Finals', po ? po.finals_appearances : '\u2026']]
    : [['Season', data.season!], ['Record', `${fmtInt(data.w)}-${fmtInt(data.l)}`],
       ['Win %', data.winPct != null ? (data.winPct * 100).toFixed(1) + '%' : '\u2014'],
       ['Playoffs', thisSeason ? thisSeason.result : data.playoffs ? 'Yes' : 'Missed'], ['Series', thisSeason ? `${thisSeason.series_won}-${thisSeason.series_lost}` : '\u2014']];
  return (
    <div className="panel compare-team-card" id={id}>
      <div className="cmp-card-name">{data.displayName}</div>
      <div className="cmp-card-meta">{career ? `${data.minSeason}\u2013${data.maxSeason}` : 'Single season'}{data.status !== 'active' ? ' \u00b7 no longer in the NBA' : ''}</div>
      <div className="cmp-card-stat-grid">{cells.map(([l, v]) => <div className="cs-cell" key={l}><div className="v">{v}</div><div className="l">{l}</div></div>)}</div>
    </div>
  );
}

function Accomplishments({ franchise, data, po }: { franchise: Franchise; data: Aggregate; po?: TeamPlayoffs }) {
  const career = data.season == null;
  const { data: honors, error } = useApi<TeamHonors>(`/teams/${enc(franchise.name)}/honors${career ? '' : `?season=${data.season}`}`);
  const [open, setOpen] = useState(false);
  const playoffLine = career
    ? `${data.playoffs} of ${data.seasons} seasons reached the playoffs${po ? ` \u00b7 ${po.titles.length} championships` : ''}`
    : (po?.seasons.find(s => s.season === data.season)?.result ?? (data.playoffs ? 'Reached the playoffs this season' : 'Missed the playoffs this season'));

  const pills = useMemo(() => {
    if (!honors) return [];
    const yr = (s: number) => (career ? ` (${s})` : '');
    return [
      ...honors.awards.map(w => ({ cls: 'won', trophy: true, text: `${AWARD_LABELS[w.award] || w.award} \u2014 ${w.player}${yr(w.season)}` })),
      ...honors.all_league_teams.map(e => ({ cls: 'won', trophy: false, text: `${teamLabel(e.team_type, e.team_number)} \u2014 ${e.player}${yr(e.season)}` })),
      ...honors.all_stars.map(s => ({ cls: 'won allstar-pill', trophy: false, text: `\u2605 All-Star \u2014 ${s.player}${yr(s.season)}` })),
    ];
  }, [honors, career]);

  const summary = useMemo(() => {
    if (!honors) return [];
    const count = (labels: string[]) => labels.reduce<Record<string, number>>((m, l) => ({ ...m, [l]: (m[l] || 0) + 1 }), {});
    return [
      ...Object.entries(count(honors.awards.map(w => AWARD_SHORT[w.award] || w.award))).map(([l, n]) => `\u{1F3C6} ${n}\u00d7 ${l}`),
      ...(honors.all_stars.length ? [`\u2605 ${honors.all_stars.length}\u00d7 All-Star`] : []),
      ...Object.entries(count(honors.all_league_teams.map(e => teamLabel(e.team_type, e.team_number)))).map(([l, n]) => `${n}\u00d7 ${l}`),
    ];
  }, [honors]);

  return (
    <div className="cmp-accomplishments-col">
      <div className="cmp-accomplishments-name">{data.displayName}</div>
      <div className="cmp-accomplishments-line">{playoffLine}</div>
      {error && <ErrorNote error={error} />}
      {!honors && !error && <Loading />}
      {honors && pills.length === 0 && <NoData>No major individual awards, All-Stars or All-NBA/All-Defense selections {career ? 'on record' : 'this season'}.</NoData>}
      {honors && pills.length > 0 && !career && (
        <div className="cmp-accomplishments-pills">{pills.map((p, i) => <span key={i} className={`award-pill ${p.cls}`}>{p.trophy && <span className="award-trophy">{'\u{1F3C6}'}</span>}{p.text}</span>)}</div>
      )}
      {honors && pills.length > 0 && career && (
        <>
          <div className="cmp-acc-summary">{summary.map(s => <span key={s} className="award-summary-badge">{s}</span>)}</div>
          <button type="button" className="cmp-acc-expand-btn" onClick={() => setOpen(o => !o)}>
            {open ? 'Collapse \u25b4' : `Show all ${pills.length} honors \u25be`}
          </button>
          {open && <div className="cmp-accomplishments-pills" style={{ marginTop: 10 }}>
            {pills.map((p, i) => <span key={i} className={`award-pill ${p.cls}`}>{p.trophy && <span className="award-trophy">{'\u{1F3C6}'}</span>}{p.text}</span>)}
          </div>}
        </>
      )}
    </div>
  );
}
