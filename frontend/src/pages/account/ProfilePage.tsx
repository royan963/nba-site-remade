import { Link, useParams } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { Profile } from '../../api/types';
import { useAuth } from '../../auth';
import { ErrorNote, Loading, NoData, Panel, SectionHead } from '../../components/ui';

const since = (t: number) => new Date(t * 1000).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

export default function ProfilePage() {
  const { username = '' } = useParams();
  const { user } = useAuth();
  const { data, error } = useApi<Profile>(`/users/${encodeURIComponent(username)}`, { fresh: true });
  const mine = user?.username === username.toLowerCase();
  if (error) return <section className="view active"><ErrorNote error={error} /></section>;
  if (!data) return <section className="view active"><Loading /></section>;
  return (
    <section className="view active" id="view-profile">
      <Panel>
        <div className="player-header">
          <div>
            <h1 className="player-name">{data.user.display_name}</h1>
            <div className="player-meta">@{data.user.username} &middot; member since {since(data.user.created_at)}</div>
            {data.user.bio && <p className="profile-bio">{data.user.bio}</p>}
          </div>
          {mine && <Link className="pill-btn" to="/account">Edit profile</Link>}
        </div>
      </Panel>
      <div className="panel-row">
        <Panel>
          <SectionHead title="Lineups" small />
          {data.lineups.length === 0 && <NoData>{mine ? 'Your public lineups show up here.' : 'No public lineups yet.'}</NoData>}
          {data.lineups.map(l => (
            <Link key={l.id} to={`/lineups/${l.id}`} className="saved-row link-row">
              <span>{l.name}</span><span className="lineup-score-pill">{l.overall ?? '\u2014'}</span>
            </Link>
          ))}
        </Panel>
        <Panel>
          <SectionHead title="Comparisons" small />
          {data.comparisons.length === 0 && <NoData>{mine ? 'Comparisons you mark public show up here.' : 'No public comparisons yet.'}</NoData>}
          {data.comparisons.map(c => (
            <Link key={c.id} to={c.path} className="saved-row link-row">
              <span>{c.title}{c.note && <span className="similar-meta"> &middot; {c.note}</span>}</span>
            </Link>
          ))}
        </Panel>
      </div>
    </section>
  );
}
