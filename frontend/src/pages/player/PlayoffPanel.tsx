import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { Meta, PlayerPlayoffs } from '../../api/types';
import { Panel, SectionHead } from '../../components/ui';
import { DASH, fmtNum, fmtPct } from '../../lib/format';

export function ResultChip({ result }: { result: string | null }) {
  if (!result) return <>{DASH}</>;
  return <span className={`result-chip ${result === 'Champion' ? 'champion' : result.includes('Finals') && result.startsWith('Lost in Finals') ? 'finalist' : ''}`}>
    {result === 'Champion' ? '\u{1F3C6} Champion' : result}</span>;
}

/** Says where playoff data ends, only when it lags the regular season. Player stats and series results end at different seasons. */
export function CoverageNote({ kind = 'players' }: { kind?: 'players' | 'teams' }) {
  const { data: meta } = useApi<Meta>('/meta');
  if (!meta) return null;
  const through = kind === 'players' ? meta.playoffs_through : meta.series_through;
  if (!through || through >= meta.latest_season) return null;
  return (
    <p className="section-sub coverage-note">
      {kind === 'players'
        ? <>Player playoff stats run through the {through} playoffs. Player stats for {through + 1}&ndash;{meta.latest_season} aren&rsquo;t available (the source data for those seasons omits many players); series results, championships and rings run through {meta.series_through}.</>
        : <>Playoff results run through the {through} playoffs.</>}
    </p>
  );
}

/** Season-by-season playoff stats with each season's result, and the career line. */
export function PlayoffPanel({ playoffs }: { playoffs: PlayerPlayoffs }) {
  if (!playoffs.seasons.length) return null;
  const c = playoffs.career!;
  return (
    <Panel id="pc-playoffs-panel">
      <SectionHead title="Playoffs" small>
        Playoff stats by season, from game-by-game box scores. Stats the era didn&rsquo;t record (rebounds before 1951, assists before 1970s, minutes in some early games) are left blank, not counted as zero.
      </SectionHead>
      <div className="table-scroll">
        <table className="lb-table" id="pc-playoffs-table">
          <thead><tr><th>Season</th><th>Team</th><th>Result</th><th>GP</th><th>MPG</th><th>PPG</th><th>RPG</th><th>APG</th><th>FG%</th><th>3P%</th><th>FT%</th></tr></thead>
          <tbody>
            {playoffs.seasons.map(s => (
              <tr key={s.season + s.team} className={s.result === 'Champion' ? 'mvp-winner' : ''}>
                <td>{s.season}</td><td>{s.team_name ?? s.team}</td><td><ResultChip result={s.result} /></td>
                <td>{s.g}</td><td>{fmtNum(s.mpg)}</td><td>{fmtNum(s.ppg)}</td><td>{fmtNum(s.rpg)}</td><td>{fmtNum(s.apg)}</td>
                <td>{fmtPct(s.fg_pct)}</td><td>{fmtPct(s.x3p_pct)}</td><td>{fmtPct(s.ft_pct)}</td>
              </tr>
            ))}
            <tr className="career-row">
              <td colSpan={3}><b>Career</b> <span className="similar-meta">{playoffs.titles.length > 0 && `${playoffs.titles.length}\u00d7 champion`}</span></td>
              <td>{c.g}</td><td>{fmtNum(c.mpg)}</td><td>{fmtNum(c.ppg)}</td><td>{fmtNum(c.rpg)}</td><td>{fmtNum(c.apg)}</td>
              <td>{fmtPct(c.fg_pct)}</td><td>{fmtPct(c.x3p_pct)}</td><td>{fmtPct(c.ft_pct)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <CoverageNote />
      <p className="section-sub" style={{ margin: '8px 0 0' }}>
        Rings count every season he was on the champion&rsquo;s roster, including players who didn&rsquo;t play, and are checked against official counts. <Link to="/teams?view=champions">See every champion</Link>.
      </p>
    </Panel>
  );
}
