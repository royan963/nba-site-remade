import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../api/hooks';
import type { RecentGame, RecentGames as RecentGamesData, RecentSide, RecentTop } from '../api/types';
import { ErrorNote, Loading, Panel, Pills, SectionHead } from '../components/ui';
import { dateHeading, groupByDate, kindLabel, otLabel, topLine } from '../lib/recentGames';
import { slugify } from './teams/geo';

const WINDOWS = [{ value: '3', label: 'Last 3 game days' }, { value: '7', label: 'Last 7' }];

/** The latest days with games: scores, who won, overtimes, and each team's top scorer. */
export function RecentGames() {
  const [days, setDays] = useState('3');
  const { data, error } = useApi<RecentGamesData>(`/games/recent?dates=${days}`);
  return (
    <Panel id="recent-games">
      <SectionHead title="Recent games">
        The latest days with games, newest first. Top scorers appear once a game&rsquo;s player stats are in. Play-in games and the NBA Cup final are shown but don&rsquo;t count in regular-season stats.
      </SectionHead>
      <Pills options={WINDOWS} value={days} onChange={setDays} id="recent-games-window" />
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      {data && data.games.length === 0 && <div className="no-data-note">No games yet.</div>}
      {data && groupByDate(data.games).map(day => (
        <div key={day.date} className="rg-day" data-date={day.date}>
          <h3 className="rg-date">{dateHeading(day.date)} <span>{day.games.length} {day.games.length === 1 ? 'game' : 'games'}</span></h3>
          <div className="rg-grid">
            {day.games.map(g => <GameCard key={g.game_ref} g={g} />)}
          </div>
        </div>
      ))}
    </Panel>
  );
}

function TeamRow({ side, won }: { side: RecentSide; won: boolean }) {
  return (
    <div className={`rg-team ${won ? 'won' : ''}`}>
      {side.franchise ? <Link to={`/teams/${slugify(side.franchise)}`} className="rg-name">{side.name}</Link> : <span className="rg-name">{side.name}</span>}
      <span className="rg-score">{side.pts ?? '—'}</span>
    </div>
  );
}

function Top({ top, abbr }: { top: RecentTop | null; abbr: string }) {
  const line = topLine(top);
  if (!top || !line) return null;
  return <div className="rg-top"><span className="rg-abbr">{abbr}</span><Link to={`/players/${top.player_id}`} className="name-link">{line}</Link></div>;
}

function GameCard({ g }: { g: RecentGame }) {
  const badge = kindLabel(g.kind);
  const ot = otLabel(g.ot);
  const hasTop = g.top.home || g.top.away;
  return (
    <div className="rg-card" data-game={g.game_ref} data-kind={g.kind}>
      <div className="rg-card-head">
        <span>{ot ? `Final/${ot}` : 'Final'}</span>
        {badge && <span className={`rg-badge ${g.kind}`}>{badge}</span>}
      </div>
      <TeamRow side={g.away} won={g.winner === 'away'} />
      <TeamRow side={g.home} won={g.winner === 'home'} />
      {hasTop
        ? <div className="rg-tops"><Top top={g.top.away} abbr={g.away.abbr} /><Top top={g.top.home} abbr={g.home.abbr} /></div>
        : <div className="rg-tops muted">Player stats not in yet</div>}
    </div>
  );
}
