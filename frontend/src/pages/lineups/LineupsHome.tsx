import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { LineupSummary } from '../../api/types';
import { useAuth } from '../../auth';
import { Loading, NoData, Panel, SectionHead } from '../../components/ui';
import { PRESETS } from './picks';

function LineupList({ items, showOwner }: { items: LineupSummary[]; showOwner?: boolean }) {
  return (
    <>
      {items.map(l => (
        <Link key={l.id} to={`/lineups/${l.id}`} className="saved-row link-row">
          <span>{l.name}{!l.is_public && <span className="hof-badge">Private</span>}
            {showOwner && l.owner && <span className="similar-meta"> &middot; {l.owner.display_name}</span>}</span>
          <span className="lineup-score-pill">{l.overall ?? '\u2014'}</span>
        </Link>
      ))}
    </>
  );
}

export default function LineupsHome() {
  const { user, ready } = useAuth();
  const { data: mine } = useApi<LineupSummary[]>(user ? '/me/lineups' : null, { fresh: true });
  const { data: shared } = useApi<LineupSummary[]>('/lineups/public?limit=12', { fresh: true });
  return (
    <section className="view active" id="view-lineups">
      <SectionHead title="All-Time Lineups">
        Put any five players from any era on the floor together. Every season is rated against its own league, then the lineup is scored on talent, skills and fit, and graded against every real NBA starting five since 1951-52.
      </SectionHead>
      <Panel>
        <div className="form-row">
          <Link className="pill-btn active" to="/lineups/new" id="new-lineup">Build a lineup</Link>
          {PRESETS.map(p => <Link key={p.label} className="pill-btn" to={`/lineups/new?p=${p.p}`}>{p.label}</Link>)}
        </div>
      </Panel>
      <div className="panel-row">
        <Panel id="my-lineups">
          <SectionHead title="My lineups" small />
          {!ready ? <Loading /> : !user ? <NoData><Link to="/login?next=/lineups">Sign in</Link> to save lineups.</NoData>
            : !mine ? <Loading /> : mine.length === 0 ? <NoData>No saved lineups yet.</NoData> : <LineupList items={mine} />}
        </Panel>
        <Panel id="shared-lineups">
          <SectionHead title="Recently shared" small />
          {!shared ? <Loading /> : shared.length === 0 ? <NoData>No public lineups yet. Be the first.</NoData> : <LineupList items={shared} showOwner />}
        </Panel>
      </div>
    </section>
  );
}
