import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { enc } from '../api/client';
import { useApi } from '../api/hooks';
import type { SearchResponse } from '../api/types';
import { ErrorNote, HofBadge, Loading, NoData, Panel, Pills, SectionHead } from '../components/ui';
import { DASH, fmtInt, fmtNum, fmtSigned } from '../lib/format';
import { roleColor } from './models/archetypeColors';

const STARTERS = ['best rebounding guards of the 90s', 'players who averaged 25 and 10 since 2010', 'top 10 three point shooters in 2016',
                  'stretch bigs of the 2010s', '50/40/90 seasons', 'Celtics leading scorers in the 80s', 'triple-double seasons',
                  'rookies with the most points', 'all-time leading scorers', 'worst free throw shooters'];

function formatValue(r: SearchResponse, v: number | null) {
  if (v == null) return DASH;
  if (r.stat_is_pct) return `${(v * 100).toFixed(1)}%`;
  if (r.stat === 'bpm') return fmtSigned(v);
  if (r.scope === 'careers' && !['ws', 'vorp'].includes(r.stat)) return fmtInt(v);
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
      <SectionHead title="Ask the stats">Type a question in plain English. It&rsquo;s read into filters you can see and remove below.</SectionHead>
      <form className="search-big" onSubmit={e => { e.preventDefault(); if (text.trim()) go(text.trim()); }}>
        <input type="search" id="search-input" value={text} onChange={e => setText(e.target.value)} autoFocus
               placeholder={'e.g. best rebounding guards of the 90s'} />
        <button type="submit" className="pill-btn active">Search</button>
      </form>

      {!q && <Starters onPick={go} />}
      {error && <ErrorNote error={error} />}
      {q && !data && !error && <Loading />}
      {data && (
        <div style={{ opacity: loading ? 0.6 : 1 }}>
          {data.understood && (
            <Panel id="search-interpretation">
              <div className="search-reading">
                <span className="pbp-subhead" style={{ margin: 0 }}>Showing</span>
                <Pills options={[{ value: 'seasons', label: 'Player-seasons' }, { value: 'careers', label: 'Careers' }]} value={data.scope} onChange={setScope} />
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
          {!data.understood && data.name_matches.length === 0 && (
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

function Results({ data }: { data: SearchResponse }) {
  if (!data.results.length) return <Panel><NoData>No {data.scope === 'careers' ? 'careers' : 'seasons'} match all of these filters. Try removing one.</NoData></Panel>;
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
                    <td>{r.season as number}</td><td>{r.team as string}</td><td>{n('age') ?? DASH}</td><td>{(r.pos as string) || DASH}</td>
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
