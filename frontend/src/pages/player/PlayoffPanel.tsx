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
  const partial = kind === 'players' ? meta.playoffs_partial ?? [] : [];
  const lags = !!through && through < meta.latest_season;
  if (!lags && !partial.length) return null;
  return (
    <p className="section-sub coverage-note">
      {lags && (kind === 'players'
        ? <>Player playoff stats run through the {through} playoffs; series results, championships and rings run through {meta.series_through}. </>
        : <>Playoff results run through the {through} playoffs. </>)}
      {partial.length > 0 && <>No box scores exist for the {partial.join(', ')} playoffs, so those stats come from series totals: right for the players listed, but some players are missing.</>}
    </p>
  );
}

/** Explains seasons that come from sources other than full box scores. */
function SourceNotes({ seasons }: { seasons: PlayerPlayoffs['seasons'] }) {
  const series = [...new Set(seasons.filter(s => s.source === 'series').map(s => s.season))];
  const logs = [...new Set(seasons.filter(s => s.source === 'game_log').map(s => s.season))];
  if (!series.length && !logs.length) return null;
  return (
    <p className="section-sub coverage-note" id="pc-playoffs-sources">
      {series.length > 0 && <>* {series.join(', ')}: from series-by-series totals rather than box scores. </>}
      {logs.length > 0 && <>{logs.join(', ')}: from game logs, which don&rsquo;t record minutes (and some games lack assists, so averages use the games that have them).</>}
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
                <td>{s.season}{s.source === 'series' && <span title="From series-by-series totals">*</span>}</td><td>{s.team_name ?? s.team}</td><td><ResultChip result={s.result} /></td>
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
      <SourceNotes seasons={playoffs.seasons} />
      <p className="section-sub" style={{ margin: '8px 0 0' }}>
        Rings count every season he was on the champion&rsquo;s roster, including players who didn&rsquo;t play, and are checked against official counts. <Link to="/teams?view=champions">See every champion</Link>.
      </p>
    </Panel>
  );
}
