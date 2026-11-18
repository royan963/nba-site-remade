import { Link } from 'react-router-dom';
import { useApi } from '../api/hooks';
import type { NewsItem, NewsResponse } from '../api/types';
import { slugify } from '../pages/teams/geo';
import { Loading, NoData, Panel, SectionHead } from './ui';

/** "12m ago", "3h ago", "Nov 14". */
export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const m = Math.max(0, Math.round((now - t) / 60000));
  if (m < 60) return `${m || 1}m ago`;
  if (m < 24 * 60) return `${Math.round(m / 60)}h ago`;
  return new Date(t).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Headlines, each linking to the publisher's story, with chips for the players and teams it mentions. */
export function NewsList({ items, compact }: { items: NewsItem[]; compact?: boolean }) {
  return (
    <ul className={`news-list${compact ? ' compact' : ''}`}>
      {items.map(i => (
        <li className="news-item" key={i.link}>
          <a className="news-title" href={i.link} target="_blank" rel="noopener noreferrer nofollow">{i.title}</a>
          <div className="news-meta">{i.source}{i.published && <> &middot; <time dateTime={i.published}>{ago(i.published)}</time></>}</div>
          {!compact && i.summary && <p className="news-summary">{i.summary}</p>}
          {(i.players.length > 0 || i.teams.length > 0) && (
            <div className="news-tags">
              {i.players.slice(0, 4).map(p => <Link key={p.player_id} className="news-chip" to={`/players/${p.player_id}`}>{p.player}</Link>)}
              {i.teams.slice(0, 3).map(t => <Link key={t.abbr} className="news-chip team" to={`/teams/${slugify(t.franchise)}`}>{t.abbr}</Link>)}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export const SOURCES_NOTE = 'Headlines from ESPN, Yahoo Sports and CBS Sports, refreshed every 15 minutes. Each one opens the full story on the publisher’s site.';

/** A player's or a team's latest headlines; renders nothing for players and teams that aren't in the league now. */
export function NewsBox({ team, player, name, id, bare }: { team?: string; player?: string; name: string; id: string; bare?: boolean }) {
  const q = team ? `team=${encodeURIComponent(team)}` : `player=${encodeURIComponent(player ?? '')}`;
  const { data, error } = useApi<NewsResponse>(`/news?${q}&limit=6`);
  if (error) return null;                                  // not a current player or team (404), or the feeds are down
  const Wrap = bare ? 'section' : Panel;
  return (
    <Wrap id={id} className="news-box">
      <SectionHead title={`${name} in the news`} small>
        {SOURCES_NOTE}{' '}
        <Link to={`/?${team ? `news_team=${encodeURIComponent(team)}` : `news_player=${encodeURIComponent(player ?? '')}`}#latest-news`}>All headlines &rarr;</Link>
      </SectionHead>
      {!data ? <Loading /> : data.items.length === 0
        ? <NoData>No headlines about {name} in the latest stories.</NoData>
        : <NewsList items={data.items} compact />}
    </Wrap>
  );
}
