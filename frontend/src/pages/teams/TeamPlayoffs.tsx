import { Link } from 'react-router-dom';
import { enc } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { TeamPlayoffs as TeamPlayoffsData } from '../../api/types';
import { ErrorNote, Loading, SectionHead } from '../../components/ui';
import { ResultChip, CoverageNote } from '../player/PlayoffPanel';
import type { Franchise } from './geo';

/** Championships, Finals trips and every playoff season's result for one franchise. */
export function TeamPlayoffs({ franchise }: { franchise: Franchise }) {
  const { data, error } = useApi<TeamPlayoffsData>(`/teams/${enc(franchise.name)}/playoffs`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const cells: [string, string | number][] = [
    ['Championships', data.titles.length], ['Finals appearances', data.finals_appearances],
    ['Playoff seasons', data.playoff_seasons], ['Series record', `${data.series_won}-${data.series_lost}`],
  ];
  const names = new Set(data.seasons.map(s => s.team_name));
  return (
    <div className="roster-section" id="team-playoffs">
      <SectionHead title="Playoff history" small />
      <div className="player-stat-row" id="team-playoff-summary">
        {cells.map(([l, v]) => <div className="ps-cell" key={l}><div className="v">{v}</div><div className="l">{l}</div></div>)}
      </div>
      {data.titles.length > 0 && (
        <div className="title-years" id="team-title-years">
          <span className="award-trophy">{'\u{1F3C6}'}</span>
          {data.titles.map(y => <span key={y} className="award-pill won">{y}</span>)}
        </div>
      )}
      {data.seasons.length === 0 ? <p className="section-sub">This franchise never reached the playoffs.</p> : (
        <div className="table-scroll" style={{ maxHeight: 340 }}>
          <table className="lb-table">
            <thead><tr><th>Season</th>{names.size > 1 && <th>Team</th>}<th>Result</th><th>Series</th><th>Games</th></tr></thead>
            <tbody>
              {[...data.seasons].reverse().map(s => (
                <tr key={s.season + s.team} className={s.champion ? 'mvp-winner' : ''}>
                  <td>{s.season}</td>{names.size > 1 && <td>{s.team_name}</td>}<td><ResultChip result={s.result} /></td>
                  <td>{s.series_won}-{s.series_lost}</td><td>{s.games_won}-{s.games_lost}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <CoverageNote kind="teams" />
      <p className="section-sub" style={{ margin: '8px 0 0' }}>Seasons are labeled by the year they ended. <Link to="/teams?view=champions">See every champion</Link>.</p>
    </div>
  );
}
