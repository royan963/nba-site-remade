import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { apiSend } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { Lineup } from '../../api/types';
import { ErrorNote, Loading, Panel } from '../../components/ui';
import { formatPicks } from './picks';
import { HowItWorks, LineupScoreView } from './LineupScore';

export default function LineupView() {
  const { lineupId = '' } = useParams();
  const navigate = useNavigate();
  const [reload, setReload] = useState(0);
  const [copied, setCopied] = useState(false);
  const { data, error } = useApi<Lineup>(`/lineups/${lineupId}`, { fresh: true, reloadKey: reload });
  if (error) return <section className="view active"><ErrorNote error={error} /></section>;
  if (!data) return <section className="view active"><Loading /></section>;
  const remix = `/lineups/new?p=${formatPicks(data.score.players.map(p => ({ player_id: p.player_id, season: p.season })))}`;

  return (
    <section className="view active" id="view-lineup">
      <Panel>
        <div className="player-header">
          <div>
            <h1 className="player-name" id="lineup-title">{data.name}</h1>
            <div className="player-meta">
              by <Link to={`/u/${data.owner.username}`}>{data.owner.display_name}</Link> &middot; updated {new Date(data.updated_at * 1000).toLocaleDateString()}
              {!data.is_public && <> &middot; <span className="hof-badge">Private</span></>}
            </div>
            {data.description && <p className="profile-bio">{data.description}</p>}
          </div>
          <div className="form-row">
            {data.is_public && (
              <button type="button" className="pill-btn" onClick={() => { navigator.clipboard?.writeText(window.location.href); setCopied(true); }}>
                {copied ? 'Link copied' : 'Copy link'}</button>
            )}
            <Link className="pill-btn" to={remix}>Remix</Link>
            {data.mine && <>
              <Link className="pill-btn" to={`/lineups/${data.id}/edit`} id="lineup-edit">Edit</Link>
              <button type="button" className="pill-btn" onClick={async () => { await apiSend('PUT', `/lineups/${data.id}`, {
                name: data.name, description: data.description, is_public: !data.is_public,
                players: data.score.players.map(p => ({ player_id: p.player_id, season: p.season })) }); setReload(r => r + 1); }}>
                {data.is_public ? 'Make private' : 'Make public'}</button>
              <button type="button" className="pill-btn danger" onClick={async () => {
                if (!window.confirm(`Delete \u201c${data.name}\u201d?`)) return;
                await apiSend('DELETE', `/lineups/${data.id}`); navigate('/lineups'); }}>Delete</button>
            </>}
          </div>
        </div>
      </Panel>
      <Panel>
        <LineupScoreView score={data.score} />
        <HowItWorks />
      </Panel>
    </section>
  );
}
