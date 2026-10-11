import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { ProjectionModel, ProjectionRow } from '../../api/types';
import { ErrorNote, HofBadge, Loading, Panel, SectionHead } from '../../components/ui';
import { fmtNum } from '../../lib/format';

export function ProjectionsPage() {
  const { data, error } = useApi<ProjectionModel>('/models/projections');
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const next = data.latest_season + 1;
  return (
    <div id="projections-page">
      <Panel id="projection-accuracy">
        <SectionHead title="How accurate is it?" small>
          Seasons {data.metrics.seasons} projected using only comparables whose careers had already played out by then, then checked against what really happened. Average miss in points per game (lower is better):
        </SectionHead>
        <div className="table-scroll">
          <table className="lb-table">
            <thead><tr><th>Seasons ahead</th><th>This model</th><th>&ldquo;Same as last season&rdquo;</th><th>League aging curve</th><th>60% range held</th><th>REB / AST miss</th><th>&ldquo;Still playing&rdquo; accuracy</th></tr></thead>
            <tbody>
              {data.metrics.horizons.map(h => (
                <tr key={h.h}>
                  <td>{h.h}</td>
                  <td><b>{h.pts.model.toFixed(2)}</b></td><td>{h.pts.last_season.toFixed(2)}</td><td>{h.pts.aging_curve.toFixed(2)}</td>
                  <td>{Math.round(h.pts.band_coverage * 100)}%</td>
                  <td>{h.trb.model.toFixed(2)} / {h.ast.model.toFixed(2)}</td>
                  <td title="Brier score; lower is better">{h.active_brier.toFixed(3)} <span className="similar-meta">vs {h.active_brier_base.toFixed(3)} base rate</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="section-sub" style={{ margin: '10px 0 0' }}>The advantage grows with distance: one season out, &ldquo;same as last season&rdquo; is hard to beat; three seasons out, knowing how similar careers aged matters most.</p>
      </Panel>

      <div className="panel-row">
        <ProjectionList id="proj-risers" title={`Biggest projected risers, ${next}`} rows={data.risers} change />
        <ProjectionList id="proj-decliners" title={`Biggest projected decliners, ${next}`} rows={data.decliners} change />
      </div>
      <ProjectionList id="proj-top" title={`Projected top scorers, ${next}`} rows={data.top_scorers} />

      <details className="lineup-notes">
        <summary>How it works</summary>
        <p>For each player in {data.latest_season}, the model finds the {data.method.k} most similar player-seasons at the same age since {data.method.pool_from}: similar minutes and league-relative per-36 scoring, rebounding, playmaking and efficiency, in that season and the one before (so trajectory counts). Their changes over the next one to three seasons, weighted by similarity, give the projection; the middle 60% of their outcomes give the range; and the share who were still playing gives the chance he plays. Only comparables whose next three seasons are known are used, and a player is never compared with himself.</p>
        <p>Stats convert back to per-game numbers using {data.latest_season}&rsquo;s league environment. Projections assume he plays: injuries, trades, roles and retirement decisions aren&rsquo;t in the data.</p>
      </details>
    </div>
  );
}

function ProjectionList({ id, title, rows, change }: { id: string; title: string; rows: ProjectionRow[]; change?: boolean }) {
  return (
    <Panel id={id}>
      <SectionHead title={title} small />
      <div className="table-scroll">
        <table className="lb-table">
          <thead><tr><th>Player</th><th>Age</th><th>Now</th><th>Projected</th>{change && <th>Change</th>}<th>Plays</th></tr></thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.player_id}>
                <td className="name-cell"><Link to={`/players/${r.player_id}`}>{r.player}</Link>{r.hof && <HofBadge />}<span className="similar-meta"> {r.team}</span></td>
                <td>{r.age}</td><td>{fmtNum(r.now_pts)}</td>
                <td>{fmtNum(r.pts)}<span className="proj-range"> {fmtNum(r.pts_lo)}&ndash;{fmtNum(r.pts_hi)}</span></td>
                {change && <td className={r.change >= 0 ? 'proj-up' : 'proj-down'}>{r.change > 0 ? '+' : ''}{r.change.toFixed(1)}</td>}
                <td>{Math.round(r.p_active * 100)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
