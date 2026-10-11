import { Link } from 'react-router-dom';
import { enc } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { PlayerH2H, PlayerH2HSide, TeamH2H } from '../../api/types';
import { ErrorNote, Loading, NoData, Panel, SectionHead } from '../../components/ui';
import { DASH, fmtNum } from '../../lib/format';
import { slugify } from '../teams/geo';

function Side({ label, x, aName, bName }: { label: string; x: PlayerH2HSide; aName: string; bName: string }) {
  if (!x.games) return null;
  const stats: [string, string][] = [['pts', 'PTS'], ['trb', 'REB'], ['ast', 'AST'], ['stl', 'STL'], ['blk', 'BLK']];
  return (
    <div className="h2h-side">
      <div className="pbp-subhead">{label}: {x.games} games &middot; {aName} {x.a_wins}&ndash;{x.b_wins} {bName}</div>
      <table className="lb-table h2h-table">
        <thead><tr><th>Per game</th>{stats.map(([, l]) => <th key={l}>{l}</th>)}</tr></thead>
        <tbody>
          <tr><td>{aName}</td>{stats.map(([k]) => <td key={k}>{fmtNum(x.a[k])}</td>)}</tr>
          <tr><td>{bName}</td>{stats.map(([k]) => <td key={k}>{fmtNum(x.b[k])}</td>)}</tr>
        </tbody>
      </table>
    </div>
  );
}

/** How two players did in the games they faced each other, from the box scores. */
export function PlayerHeadToHead({ a, b, season }: { a: string; b: string; season?: number }) {
  const { data, error } = useApi<PlayerH2H>(`/head-to-head/players?a=${a}&b=${b}`);
  if (error) return <Panel id="cmp-h2h-panel"><ErrorNote error={error} /></Panel>;
  if (!data) return <Panel id="cmp-h2h-panel"><Loading /></Panel>;
  const A = data.a.player, B = data.b.player;
  const thisSeason = season ? data.meetings.filter(m => m.season === season) : [];
  return (
    <Panel id="cmp-h2h-panel">
      <SectionHead title="Head-to-head" small>
        Games where they played against each other{data.teammate_games ? `. They were teammates in ${data.teammate_games} games, which don\u2019t count here` : ''}. Wins are their teams&rsquo; results.
      </SectionHead>
      {!data.regular.games && !data.playoffs.games ? <NoData>They never played against each other{data.teammate_games ? ' (only as teammates)' : ''}.</NoData> : (
        <>
          <div className="h2h-grid">
            <Side label="Regular season" x={data.regular} aName={A} bName={B} />
            <Side label="Playoffs" x={data.playoffs} aName={A} bName={B} />
          </div>
          {season && thisSeason.length > 0 && <p className="section-sub" style={{ margin: '10px 0 0' }}>In {season}: {thisSeason.length} meeting{thisSeason.length > 1 ? 's' : ''} among the most recent shown below.</p>}
          <div className="table-scroll">
            <table className="lb-table">
              <thead><tr><th>Recent meetings</th><th>Score</th><th>{A}</th><th>{B}</th></tr></thead>
              <tbody>{data.meetings.map(m => (
                <tr key={m.game_ref} className={season && m.season === season ? 'mvp-winner' : ''}>
                  <td>{m.date}{m.playoffs && <span className="hof-badge">PO</span>}</td>
                  <td>{m.a_team} {m.a_score ?? DASH}&ndash;{m.b_score ?? DASH} {m.b_team}</td>
                  <td>{m.a.pts ?? DASH} pts, {m.a.trb ?? DASH} reb, {m.a.ast ?? DASH} ast</td>
                  <td>{m.b.pts ?? DASH} pts, {m.b.trb ?? DASH} reb, {m.b.ast ?? DASH} ast</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}

/** Two franchises' all-time record against each other, their playoff series, and recent games. */
export function TeamHeadToHead({ a, b }: { a: string; b: string }) {
  const { data, error } = useApi<TeamH2H>(`/head-to-head/teams?a=${enc(a)}&b=${enc(b)}`);
  if (error) return <Panel id="cmp-team-h2h"><ErrorNote error={error} /></Panel>;
  if (!data) return <Panel id="cmp-team-h2h"><Loading /></Panel>;
  const rec = (label: string, r: TeamH2H['regular']) => r.games > 0 && (
    <div className="ps-cell"><div className="v">{r.a_wins}&ndash;{r.b_wins}</div><div className="l">{label} ({r.games} games) &middot; {fmtNum(r.a_ppg)}&ndash;{fmtNum(r.b_ppg)} ppg</div></div>);
  return (
    <Panel id="cmp-team-h2h">
      <SectionHead title="Head-to-head" small>Every game between the two franchises{data.first_meeting ? ` since ${data.first_meeting.slice(0, 4)}` : ''}. Records are from the {a}{a.endsWith('s') ? '\u2019' : '\u2019s'} side.</SectionHead>
      {!data.regular.games && !data.playoffs.games ? <NoData>These franchises never played each other.</NoData> : (
        <>
          <div className="player-stat-row" id="cmp-team-h2h-record">
            {rec('Regular season', data.regular)}{rec('Playoffs', data.playoffs)}
            {data.series.length > 0 && <div className="ps-cell"><div className="v">{data.series_a_won}&ndash;{data.series.length - data.series_a_won}</div><div className="l">Playoff series</div></div>}
          </div>
          {data.series.length > 0 && (
            <div className="chart-controls" style={{ margin: '10px 0 14px' }}>
              {data.series.map(x => <span key={x.season + x.round} className={`award-pill ${x.winner === a ? 'won' : ''}`}>{x.season} {x.round}: {x.a_wins}&ndash;{x.b_wins}</span>)}
            </div>
          )}
          <div className="table-scroll">
            <table className="lb-table">
              <thead><tr><th>Recent games</th><th>Result</th></tr></thead>
              <tbody>{data.recent.map(g => (
                <tr key={g.game_ref}><td>{g.date}{g.playoffs && <span className="hof-badge">PO</span>}</td>
                  <td>{g.a_team} <b className={(g.a_pts ?? 0) > (g.b_pts ?? 0) ? 'proj-up' : 'proj-down'}>{g.a_pts}&ndash;{g.b_pts}</b> {g.a_home ? 'vs' : '@'} {g.b_team}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <p className="section-sub" style={{ margin: '8px 0 0' }}>See each franchise: <Link to={`/teams/${slugify(a)}`}>{a}</Link> &middot; <Link to={`/teams/${slugify(b)}`}>{b}</Link></p>
        </>
      )}
    </Panel>
  );
}
