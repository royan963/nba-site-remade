import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { enc } from '../api/client';
import { useApi } from '../api/hooks';
import type { SearchPlayerCard, SearchResponse } from '../api/types';
import { ErrorNote, HofBadge, Loading, NoData, Panel, Pills, SectionHead } from '../components/ui';
import { DASH, fmtInt, fmtMoney, fmtNum, fmtSigned, height } from '../lib/format';
import { roleColor } from './models/archetypeColors';

const STARTERS = ['how many rings does lebron have', 'curry vs harden', 'best rebounding guards of the 90s', 'most points in a playoff game',
                  'players who averaged 25 and 10 since 2010', 'who has the most championships', 'youngest MVPs', 'tallest players',
                  'highest paid players this season', '50/40/90 seasons', 'Celtics leading scorers in the 80s', 'all-time leading scorers'];

function formatValue(r: SearchResponse, v: number | null) {
  if (v == null) return DASH;
  if (r.stat_is_pct) return `${(v * 100).toFixed(1)}%`;
  if (r.stat === 'bpm' || r.stat === 'dbpm') return fmtSigned(v);
  if (r.stat === 'height') return height(v);
  if (r.stat === 'salary') return fmtMoney(v);
  if (r.stat === 'titles' || r.stat === 'age') return String(v);
  if ((r.scope === 'careers' && !r.playoffs) || r.scope === 'games') return ['ws', 'vorp'].includes(r.stat) ? fmtNum(v) : fmtInt(v);
  if (r.scope === 'careers' && r.playoffs) return fmtInt(v);
  return fmtNum(v, ['x3pm'].includes(r.stat) ? 2 : 1);
}

export default function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get('q') ?? '';
  const drop = params.getAll('drop');
  const scope = params.get('scope');
  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  const path = q ? `/search?q=${enc(q)}${drop.map(d => `&drop=${d}`).join('')}${scope ? `&scope=${scope}` : ''}` : null;
  const { data, error, loading } = useApi<SearchResponse>(path);

  const go = (query: string, extra = '') => navigate(`/search?q=${enc(query)}${extra}`);
  const remove = (index: number) => go(q, [...drop, String(index)].map(d => `&drop=${d}`).join('') + (scope ? `&scope=${scope}` : ''));
  const setScope = (v: string) => go(q, drop.map(d => `&drop=${d}`).join('') + `&scope=${v}`);

  return (
    <section className="view active" id="view-search">
      <SectionHead title="Ask the stats">Ask in plain English: about a player (&ldquo;how many rings does LeBron have&rdquo;), two players (&ldquo;Curry vs Harden&rdquo;), or a list (&ldquo;most points in a playoff game&rdquo;). The question is read into filters you can see and remove.</SectionHead>
      <form className="search-big" onSubmit={e => { e.preventDefault(); if (text.trim()) go(text.trim()); }}>
        <input type="search" id="search-input" value={text} onChange={e => setText(e.target.value)} autoFocus
               placeholder={'e.g. how many rings does LeBron have'} />
        <button type="submit" className="pill-btn active">Ask</button>
      </form>

      {!q && <Starters onPick={go} />}
      {error && <ErrorNote error={error} />}
      {q && !data && !error && <Loading />}
      {data && (
        <div style={{ opacity: loading ? 0.6 : 1 }}>
          {data.answer && <div className="search-answer" id="search-answer">{data.answer}</div>}
          {data.compare && <CompareCard compare={data.compare} />}
          {data.player && !data.understood && <PlayerCard card={data.player} />}
          {data.links && data.links.length > 0 && (
            <Panel id="search-links">
              <SectionHead title="This is answered on" small />
              <div className="chart-controls">
                {data.links.map(l => <Link key={l.url} to={l.url} className="pill-btn active">{l.label} &rarr;</Link>)}
              </div>
            </Panel>
          )}

          {data.understood && (
            <Panel id="search-interpretation">
              <div className="search-reading">
                <span className="pbp-subhead" style={{ margin: 0 }}>Showing</span>
                <Pills options={[{ value: 'seasons', label: data.playoffs ? 'Playoff runs' : 'Player-seasons' }, { value: 'careers', label: 'Careers' },
                                 { value: 'games', label: 'Single games' }]} value={data.scope} onChange={setScope} />
                <div className="search-chips" id="search-chips">
                  {data.filters.filter(f => f.kind !== 'scope').map((f, i) => (
                    <span key={i} className={`search-chip kind-${f.kind}`}>
                      {f.kind === 'stat' ? <>ranked by <b>{f.label}</b></> : f.label}
                      {f.index != null && f.kind !== 'stat' && (
                        <button type="button" aria-label={`Remove ${f.label}`} onClick={() => remove(f.index!)}>&times;</button>
                      )}
                    </span>
                  ))}
                </div>
              </div>
              {data.ignored.length > 0 && <p className="section-sub search-ignored">Didn&rsquo;t understand: {data.ignored.map(w => <code key={w}>{w}</code>)}</p>}
              {data.notes.map(n => <p key={n} className="section-sub search-ignored">{n}</p>)}
            </Panel>
          )}

          {data.name_matches.length > 0 && (
            <Panel id="search-names">
              <SectionHead title="Players" small />
              <div className="chart-controls">
                {data.name_matches.map(p => (
                  <Link key={p.player_id} to={`/players/${p.player_id}`} className="pill-btn">{p.player}{p.hof && <HofBadge />} <span className="similar-meta">{p.first_season}&ndash;{p.last_season}</span></Link>
                ))}
              </div>
            </Panel>
          )}

          {data.understood && <Results data={data} />}
          {!data.understood && !data.player && !data.compare && !data.links?.length && data.name_matches.length === 0 && (
            <Panel><NoData>Couldn&rsquo;t read that as a stats question or a player&rsquo;s name. Try one of these:</NoData><Starters onPick={go} /></Panel>
          )}
        </div>
      )}
    </section>
  );
}

function Starters({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="chart-controls search-starters" id="search-starters">
      {STARTERS.map(s => <button key={s} type="button" className="pill-btn" onClick={() => onPick(s)}>{s}</button>)}
    </div>
  );
}

const season = (s: number) => `${s - 1}-${String(s).slice(2)}`;

function facts(c: SearchPlayerCard): [string, string][] {
  return [
    ['Career', `${c.first_season}–${c.last_season}`], ['Height', height(c.height)],
    ['PPG / RPG / APG', `${fmtNum(c.ppg)} / ${fmtNum(c.rpg)} / ${fmtNum(c.apg)}`], ['Points', fmtInt(c.pts)],
    ['Championships', c.titles.length ? `${c.titles.length} (${c.titles.join(', ')})` : '0'],
    ['MVP', c.mvps.length ? `${c.mvps.length} (${c.mvps.join(', ')})` : '0'],
    ...(c.finals_mvps.length ? [['Finals MVP', `${c.finals_mvps.length} (${c.finals_mvps.join(', ')})`] as [string, string]] : []),
    ['All-Star', c.all_star ? `${c.all_star}×` : '0'],
    ...(c.salary ? [[`Salary ${season(c.salary.season)}`, fmtMoney(c.salary.amount)] as [string, string]] : []),
  ];
}

function PlayerCard({ card }: { card: SearchPlayerCard }) {
  return (
    <Panel id="search-player">
      <div className="player-header">
        <div>
          <h2 className="player-name" style={{ fontSize: 30 }}><Link to={`/players/${card.player_id}`}>{card.player}</Link>{card.hof && <HofBadge label="Hall of Fame" />}</h2>
          <div className="player-meta">{card.pos || DASH}{card.age != null && <> &middot; age {card.age} in {season(card.age_season!)}</>}</div>
        </div>
        <div className="form-row">
          <Link className="pill-btn active" to={`/players/${card.player_id}`}>Full profile &rarr;</Link>
        </div>
      </div>
      <div className="player-stat-row">
        {facts(card).map(([l, v]) => <div className="ps-cell" key={l}><div className="v" style={{ fontSize: v.length > 12 ? 16 : undefined }}>{v}</div><div className="l">{l}</div></div>)}
      </div>
      <div className="chart-controls" style={{ marginTop: 12 }}>
        {[['playoffs', 'Playoffs'], ['games', 'Game log'], ['awards', 'Awards'], ['shooting', 'Shooting'], ['contract', 'Contract']].map(([tab, label]) => (
          <Link key={tab} className="pill-btn" to={`/players/${card.player_id}?tab=${tab}`}>{label}</Link>
        ))}
      </div>
    </Panel>
  );
}

function CompareCard({ compare }: { compare: NonNullable<SearchResponse['compare']> }) {
  const [a, b] = compare.cards;
  const rows: [string, (c: SearchPlayerCard) => string, (c: SearchPlayerCard) => number][] = [
    ['Career', c => `${c.first_season}–${c.last_season}`, () => 0],
    ['Points per game', c => fmtNum(c.ppg), c => c.ppg ?? 0], ['Rebounds per game', c => fmtNum(c.rpg), c => c.rpg ?? 0],
    ['Assists per game', c => fmtNum(c.apg), c => c.apg ?? 0], ['Career points', c => fmtInt(c.pts), c => c.pts ?? 0],
    ['Win Shares', c => fmtNum(c.ws), c => c.ws ?? 0], ['Championships', c => String(c.titles.length), c => c.titles.length],
    ['MVPs', c => String(c.mvps.length), c => c.mvps.length], ['All-Star', c => String(c.all_star ?? 0), c => c.all_star ?? 0],
  ];
  return (
    <Panel id="search-compare">
      <div className="player-header">
        <SectionHead title={`${a.player} vs. ${b.player}`} small>Career at a glance. The full comparison lines them up by age, season or experience, with era-adjusted stats and head-to-head games.</SectionHead>
        <Link className="pill-btn active" to={compare.url} id="search-compare-link">Full comparison &rarr;</Link>
      </div>
      <div className="table-scroll">
        <table className="lb-table">
          <thead><tr><th></th><th><Link to={`/players/${a.player_id}`}>{a.player}</Link></th><th><Link to={`/players/${b.player_id}`}>{b.player}</Link></th></tr></thead>
          <tbody>
            {rows.map(([label, show, num]) => {
              const x = num(a), y = num(b);
              return (
                <tr key={label}>
                  <td>{label}</td>
                  <td className={x > y ? 'sorted-cell' : ''}>{show(a)}</td>
                  <td className={y > x ? 'sorted-cell' : ''}>{show(b)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Results({ data }: { data: SearchResponse }) {
  if (!data.results.length) return <Panel><NoData>No {data.scope === 'careers' ? 'careers' : data.scope === 'games' ? 'games' : 'seasons'} match all of these filters. Try removing one.</NoData></Panel>;
  if (data.scope === 'games') return <GameResults data={data} />;
  if (data.playoffs) return <PlayoffResults data={data} />;
  const seasons = data.scope === 'seasons';
  const extra = !(seasons && ['pts', 'trb', 'ast', 'mp', 'g'].includes(data.stat)) && !(!seasons && ['pts', 'trb', 'ast', 'g'].includes(data.stat));
  return (
    <Panel id="search-results">
      <div className="table-scroll">
        <table className="lb-table">
          <thead>
            <tr>
              <th>#</th><th>Player</th>
              {seasons ? <><th>Season</th><th>Team</th><th>Age</th><th>Pos</th><th>GP</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th></>
                       : <><th>Career</th><th>Pos</th><th>GP</th><th>PTS</th><th>REB</th><th>AST</th><th>PPG</th></>}
              {extra && <th className="sorted">{data.stat_label}</th>}
              {seasons && <th>Style</th>}
            </tr>
          </thead>
          <tbody id="search-tbody">
            {data.results.map((r, i) => {
              const n = (k: string) => r[k] as number | null;
              const sortedCell = (k: string) => (k === data.stat ? 'sorted-cell' : '');
              return (
                <tr key={`${r.player_id}-${r.season ?? ''}-${r.team ?? ''}`}>
                  <td className="rank-cell">{i + 1}</td>
                  <td className="name-cell"><Link to={`/players/${r.player_id}${seasons ? `?stat=${['pts', 'trb', 'ast', 'stl', 'blk', 'mp', 'per', 'ws', 'bpm', 'vorp', 'ts_pct', 'fg_pct', 'x3p_pct'].includes(data.stat) ? data.stat : 'pts'}` : ''}`}>{r.player}</Link>{r.hof && <HofBadge />}</td>
                  {seasons ? <>
                    <td>{r.season as number}</td><td>{r.team as string}</td><td className={sortedCell('age')}>{n('age') ?? DASH}</td><td>{(r.pos as string) || DASH}</td>
                    <td className={sortedCell('g')}>{n('g') ?? DASH}</td><td className={sortedCell('mp')}>{fmtNum(n('mp'))}</td>
                    <td className={sortedCell('pts')}>{fmtNum(n('pts'))}</td><td className={sortedCell('trb')}>{fmtNum(n('trb'))}</td><td className={sortedCell('ast')}>{fmtNum(n('ast'))}</td>
                  </> : <>
                    <td>{n('first_season')}&ndash;{n('last_season')}</td><td>{(r.pos as string) || DASH}</td><td className={sortedCell('g')}>{fmtInt(n('g'))}</td>
                    <td className={sortedCell('pts')}>{fmtInt(n('pts'))}</td><td className={sortedCell('trb')}>{fmtInt(n('trb'))}</td><td className={sortedCell('ast')}>{fmtInt(n('ast'))}</td><td>{fmtNum(n('ppg'))}</td>
                  </>}
                  {extra && <td className="sorted-cell">{formatValue(data, r.value)}</td>}
                  {seasons && <td>{r.archetype ? <Link to={`/models/archetypes?role=${r.archetype}`} className="style-mini" style={{ color: roleColor(r.archetype as string) }}>{r.archetype_name as string}</Link> : DASH}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.season_note && <p className="section-sub" style={{ margin: '10px 0 0' }}>{data.season_note} Minimums apply so small samples don&rsquo;t top the list (for example 40+ games, and 2+ three-point attempts a game for 3P%).</p>}
    </Panel>
  );
}

function GameResults({ data }: { data: SearchResponse }) {
  const extra = !['pts', 'trb', 'ast'].includes(data.stat);
  return (
    <Panel id="search-results">
      <div className="table-scroll">
        <table className="lb-table">
          <thead><tr><th>#</th><th>Player</th><th>Date</th><th>Team</th><th>Opp</th><th>Result</th><th>PTS</th><th>REB</th><th>AST</th>{extra && <th className="sorted">{data.stat_label}</th>}</tr></thead>
          <tbody id="search-tbody">
            {data.results.map((r, i) => (
              <tr key={`${r.player_id}-${r.date}`}>
                <td className="rank-cell">{i + 1}</td>
                <td className="name-cell"><Link to={`/players/${r.player_id}?tab=games&gl=${r.season}${r.playoffs ? '&glt=playoffs' : ''}`}>{r.player}</Link>{r.hof && <HofBadge />}</td>
                <td>{r.date as string}{r.playoffs && <span className="similar-meta"> playoffs</span>}</td><td>{r.team as string}</td>
                <td>{r.home ? '' : '@ '}{(r.opponent as string) ?? DASH}</td><td>{r.result ? `${r.result} ${r.score}` : DASH}</td>
                {(['pts', 'trb', 'ast'] as const).map(k => <td key={k} className={data.stat === k ? 'sorted-cell' : ''}>{r[k] == null ? DASH : String(r[k])}</td>)}
                {extra && <td className="sorted-cell">{formatValue(data, r.value)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-sub" style={{ margin: '10px 0 0' }}>From the game-by-game logs (every game since 1946-47 with complete box scores; no 2024-25 playoff box scores exist).</p>
    </Panel>
  );
}

function PlayoffResults({ data }: { data: SearchResponse }) {
  const seasons = data.scope === 'seasons';
  const extra = !(seasons && ['pts', 'trb', 'ast', 'g'].includes(data.stat)) && !(!seasons && ['g'].includes(data.stat));
  return (
    <Panel id="search-results">
      <div className="table-scroll">
        <table className="lb-table">
          <thead><tr><th>#</th><th>Player</th><th>{seasons ? 'Season' : 'Career'}</th>{seasons && <th>Team</th>}<th>GP</th><th>PPG</th><th>RPG</th><th>APG</th>{extra && <th className="sorted">{data.stat_label}</th>}</tr></thead>
          <tbody id="search-tbody">
            {data.results.map((r, i) => (
              <tr key={`${r.player_id}-${r.season ?? ''}`}>
                <td className="rank-cell">{i + 1}</td>
                <td className="name-cell"><Link to={`/players/${r.player_id}?tab=playoffs`}>{r.player}</Link>{r.hof && <HofBadge />}</td>
                <td>{seasons ? String(r.season) : `${r.first_season}–${r.last_season}`}</td>{seasons && <td>{r.team as string}</td>}
                <td className={data.stat === 'g' ? 'sorted-cell' : ''}>{String(r.g)}</td>
                {(['ppg', 'rpg', 'apg'] as const).map((k, j) => <td key={k} className={seasons && data.stat === ['pts', 'trb', 'ast'][j] ? 'sorted-cell' : ''}>{fmtNum(r[k] as number | null)}</td>)}
                {extra && <td className="sorted-cell">{formatValue(data, r.value)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="section-sub" style={{ margin: '10px 0 0' }}>Playoff stats from box scores; 2024-25 from series totals, which leave out some players.{seasons ? ' A playoff run needs 6+ games to be listed.' : ' Careers need 20+ playoff games.'}</p>
    </Panel>
  );
}
