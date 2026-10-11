import { useApi } from '../../api/hooks';
import type { CareerHighs, GameCoverage, GameLog as GameLogData, GameRow } from '../../api/types';
import { ErrorNote, Loading, NoData, Panel, Pills, SectionHead } from '../../components/ui';
import { DASH, fmtNum } from '../../lib/format';
import { oneOf, useQueryParam } from '../../lib/useQuery';

const v = (x: number | null | undefined) => (x == null ? DASH : String(x));
const made = (m: number | null, a: number | null) => (m == null || a == null ? DASH : `${m}-${a}`);
const opp = (g: GameRow) => `${g.home ? 'vs' : '@'} ${g.opponent}`;
const result = (g: GameRow) => (g.result ? `${g.result} ${g.score}${g.ot ? (g.ot > 1 ? ` (${g.ot}OT)` : ' (OT)') : ''}` : DASH);

/** One season's games, regular season or playoffs. */
export function GameLogPanel({ playerId }: { playerId: string }) {
  const [typeRaw, setType] = useQueryParam('glt', 'regular');
  const type = oneOf(typeRaw, ['regular', 'playoffs'] as const, 'regular');
  const [seasonRaw, setSeason] = useQueryParam('gl', '');
  const { data, error } = useApi<GameLogData>(`/players/${playerId}/gamelog?type=${type}${seasonRaw ? `&season=${seasonRaw}` : ''}`);
  const { data: cov } = useApi<GameCoverage>('/games/coverage');
  if (error) return <Panel><ErrorNote error={error} /></Panel>;
  if (!data) return <Panel><Loading /></Panel>;
  if (!data.seasons.length) return null;
  const options = data.seasons.filter(s => (type === 'playoffs' ? s.playoffs : s.regular) > 0);
  // only mention missing playoffs the player was around for
  const missing = (cov?.missing_playoffs ?? []).filter(m => data.seasons.some(s => Math.abs(s.season - m) <= 1));
  const games = data.games;
  const avg = (k: keyof GameRow) => {
    const vals = games.map(g => g[k] as number | null).filter((x): x is number => x != null);
    return vals.length ? fmtNum(vals.reduce((a, b) => a + b, 0) / vals.length) : DASH;
  };
  return (
    <Panel id="pc-gamelog-panel">
      <SectionHead title="Game log" small>Every game, from the box scores.</SectionHead>
      <div className="shot-profile-controls">
        <select id="pc-gamelog-season" value={data.season ?? ''} onChange={e => setSeason(e.target.value)}>
          {options.map(s => <option key={s.season} value={s.season}>{s.season} ({type === 'playoffs' ? s.playoffs : s.regular} games)</option>)}
          {type === 'playoffs' && missing.map(m => (
            <option key={m} value={m} disabled>{m} (not available)</option>))}
        </select>
        <Pills options={[{ value: 'regular', label: 'Regular season' }, { value: 'playoffs', label: 'Playoffs' }]} value={type}
               onChange={t => { setType(t); setSeason(''); }} id="pc-gamelog-type" />
      </div>
      {games.length === 0 ? <NoData>No {type === 'playoffs' ? 'playoff ' : ''}games this season.</NoData> : (
        <div className="table-scroll" style={{ maxHeight: 460 }}>
          <table className="lb-table gamelog-table" id="pc-gamelog-table">
            <thead><tr><th>Date</th><th>Opp</th><th>Result</th><th>MIN</th><th>PTS</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TOV</th>
              <th>FG</th><th>3P</th><th>FT</th><th>+/-</th></tr></thead>
            <tbody>
              {games.map(g => (
                <tr key={g.game_ref + g.team} className={g.src === 'dc_pbp' ? 'rebuilt' : ''}>
                  <td>{g.date}{g.src === 'dc_pbp' && <span className="rebuilt-mark" title="Rebuilt from play-by-play">&dagger;</span>}</td>
                  <td>{opp(g)}</td><td className={g.result === 'W' ? 'proj-up' : g.result === 'L' ? 'proj-down' : ''}>{result(g)}</td>
                  <td>{g.mp == null ? DASH : Math.round(g.mp)}</td><td><b>{v(g.pts)}</b></td><td>{v(g.trb)}</td><td>{v(g.ast)}</td><td>{v(g.stl)}</td><td>{v(g.blk)}</td>
                  <td>{v(g.tov)}</td><td>{made(g.fg, g.fga)}</td><td>{made(g.x3p, g.x3pa)}</td><td>{made(g.ft, g.fta)}</td>
                  <td>{g.pm == null ? DASH : (g.pm > 0 ? '+' : '') + g.pm}</td>
                </tr>
              ))}
              <tr className="career-row"><td colSpan={3}><b>Averages</b> <span className="similar-meta">{games.length} games</span></td>
                <td>{avg('mp')}</td><td>{avg('pts')}</td><td>{avg('trb')}</td><td>{avg('ast')}</td><td>{avg('stl')}</td><td>{avg('blk')}</td><td>{avg('tov')}</td>
                <td colSpan={4}></td></tr>
            </tbody>
          </table>
        </div>
      )}
      {data.rebuilt_games > 0 && (
        <p className="section-sub coverage-note">&dagger; Rebuilt from play-by-play ({data.rebuilt_games} games), where the box score was incomplete: assists, minutes, fouls and +/- aren&rsquo;t available for those games.</p>
      )}
      {type === 'playoffs' && missing.length > 0 && (
        <p className="section-sub coverage-note">Box scores for the {missing.join(', ')} playoffs aren&rsquo;t in any available dataset; those series, champions and awards are still shown.</p>
      )}
    </Panel>
  );
}

const HIGHS: [string, string][] = [['pts', 'Points'], ['trb', 'Rebounds'], ['ast', 'Assists'], ['stl', 'Steals'], ['blk', 'Blocks'], ['x3p', '3-pointers']];

/** Career highs, milestone counts and best scoring games. */
export function CareerHighsPanel({ playerId }: { playerId: string }) {
  const [typeRaw, setType] = useQueryParam('hit', 'regular');
  const type = oneOf(typeRaw, ['regular', 'playoffs'] as const, 'regular');
  const { data, error } = useApi<CareerHighs>(`/players/${playerId}/highs?type=${type}`);
  if (error) return <Panel><ErrorNote error={error} /></Panel>;
  if (!data) return <Panel><Loading /></Panel>;
  if (!data.milestones.games && type === 'regular') return null;
  const m = data.milestones;
  return (
    <Panel id="pc-highs-panel">
      <SectionHead title="Career highs" small>Best single games and milestone counts. Older box scores lack some stats (no steals or blocks before 1973-74, for example).</SectionHead>
      <Pills options={[{ value: 'regular', label: 'Regular season' }, { value: 'playoffs', label: 'Playoffs' }]} value={type} onChange={setType} id="pc-highs-type" />
      {!m.games ? <NoData>No playoff games.</NoData> : (
        <>
          <div className="player-stat-row" id="pc-highs">
            {HIGHS.map(([k, label]) => {
              const h = data.highs[k];
              return (
                <div className="ps-cell" key={k}>
                  <div className="v">{h ? h.value : DASH}</div>
                  <div className="l">{label}{h && <><br />{h.date} {opp(h)}{h.times > 1 ? ` \u00b7 ${h.times}\u00d7` : ''}</>}</div>
                </div>
              );
            })}
          </div>
          <div className="player-stat-row" id="pc-milestones">
            {[['30-point games', m.pts30], ['40-point games', m.pts40], ['50-point games', m.pts50], ['Double-doubles', m.double_doubles], ['Triple-doubles', m.triple_doubles],
              ['Games', m.games]].map(([l, x]) => <div className="ps-cell" key={l as string}><div className="v">{x}</div><div className="l">{l}</div></div>)}
          </div>
          <div className="table-scroll">
            <table className="lb-table">
              <thead><tr><th>Best scoring games</th><th>Opp</th><th>Result</th><th>PTS</th><th>REB</th><th>AST</th><th>FG</th></tr></thead>
              <tbody>{data.top_scoring_games.map(g => (
                <tr key={g.game_ref + g.team}><td>{g.date}</td><td>{opp(g)}</td><td>{result(g)}</td><td><b>{v(g.pts)}</b></td><td>{v(g.trb)}</td><td>{v(g.ast)}</td><td>{made(g.fg, g.fga)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}
