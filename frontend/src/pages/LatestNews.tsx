import { useState } from 'react';
import { useApi } from '../api/hooks';
import type { NewsResponse } from '../api/types';
import { NewsList, SOURCES_NOTE } from '../components/News';
import { ErrorNote, Loading, NoData, Panel, SectionHead } from '../components/ui';
import { useQueryParam } from '../lib/useQuery';

/** Overview: the latest NBA headlines, filterable by team or by a player in the news. */
export function LatestNews() {
  const [team, setTeam] = useQueryParam('news_team', '');
  const [player, setPlayer] = useQueryParam('news_player', '');
  const [shown, setShown] = useState(12);
  const q = new URLSearchParams({ limit: '40', ...(team ? { team } : {}), ...(player ? { player } : {}) });
  const { data, error } = useApi<NewsResponse>(`/news?${q}`);
  // the lists for the pickers come from the unfiltered call, so they stay complete while a filter is on
  const { data: all } = useApi<NewsResponse>(team || player ? '/news?limit=1' : null);
  const lists = all ?? data;
  const failed = (data?.sources ?? []).filter(s => !s.ok).map(s => s.name);
  const teamName = lists?.teams.find(t => t.abbr === team)?.team_name;
  const playerName = lists?.players_in_news.find(p => p.player_id === player)?.player;
  return (
    <Panel id="latest-news">
      <div className="player-header">
        <div><SectionHead title="Latest news" small>{SOURCES_NOTE}</SectionHead></div>
        <div className="form-row news-filters">
          <select id="news-team" aria-label="Team news" value={team} onChange={e => { setPlayer(''); setTeam(e.target.value); }}>
            <option value="">All teams</option>
            {lists?.teams.map(t => <option key={t.abbr} value={t.abbr}>{t.team_name}</option>)}
          </select>
          <select id="news-player" aria-label="Player news" value={player} onChange={e => { setTeam(''); setPlayer(e.target.value); }}>
            <option value="">Players in the news</option>
            {player && !lists?.players_in_news.some(p => p.player_id === player) && <option value={player}>{player}</option>}
            {lists?.players_in_news.map(p => <option key={p.player_id} value={p.player_id}>{p.player} ({p.stories})</option>)}
          </select>
          {(team || player) && <button type="button" className="pill-btn" id="news-clear" onClick={() => { setTeam(''); setPlayer(''); }}>Show all</button>}
        </div>
      </div>
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading text="Loading headlines…" />}
      {data && (team || player) && <p className="section-sub" id="news-filter-note">Stories about <b>{teamName ?? playerName ?? team ?? player}</b>: {data.items.length}</p>}
      {data && data.items.length === 0 && <NoData>No headlines {team || player ? 'about that right now' : 'right now'}.</NoData>}
      {data && data.items.length > 0 && <NewsList items={data.items.slice(0, shown)} />}
      {data && data.items.length > shown && (
        <button type="button" className="pill-btn" id="news-more" style={{ marginTop: 12 }} onClick={() => setShown(n => n + 12)}>
          Show more ({data.items.length - shown} more)
        </button>
      )}
      {failed.length > 0 && <p className="section-sub" style={{ marginBottom: 0 }}>Couldn&rsquo;t reach {failed.join(' and ')} just now; showing the rest.</p>}
    </Panel>
  );
}
