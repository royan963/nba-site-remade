import { Link } from 'react-router-dom';
import type { PlayerProjection } from '../../api/types';
import { HofBadge, Panel, SectionHead } from '../../components/ui';
import { DASH, fmtNum } from '../../lib/format';

const range = (v: number | null, lo: number | null, hi: number | null) =>
  v == null ? DASH : <>{fmtNum(v)}<span className="proj-range"> {fmtNum(lo)}&ndash;{fmtNum(hi)}</span></>;

/** Next three seasons for a current player (only shown for players active in the latest season). */
export function ProjectionPanel({ projection }: { projection: PlayerProjection }) {
  if (!projection.projected) return null;
  return (
    <Panel id="pc-projection-panel">
      <SectionHead title="Projection" small>
        From how the most similar players at the same age actually developed. The small numbers are the range that held 60% of those outcomes; the projection assumes he plays.{' '}
        <Link to="/models/projections">How accurate is this?</Link>
      </SectionHead>
      <div className="table-scroll">
        <table className="lb-table" id="pc-projection-table">
          <thead><tr><th>Season</th><th>Age</th><th>Chance he plays</th><th>PTS</th><th>REB</th><th>AST</th><th>MIN</th><th>TS%</th></tr></thead>
          <tbody>
            {projection.horizons.map(h => (
              <tr key={h.season}>
                <td>{h.season}</td><td>{h.age ?? DASH}</td>
                <td><div className="mvp-share"><div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${h.p_active * 100}%` }} /></div>
                  <span>{Math.round(h.p_active * 100)}%</span></div></td>
                {h.pts == null
                  ? <td colSpan={5} className="similar-meta">Too few comparable players were still playing at this age to project.</td>
                  : <><td>{range(h.pts, h.pts_lo, h.pts_hi)}</td><td>{range(h.trb, h.trb_lo, h.trb_hi)}</td><td>{range(h.ast, h.ast_lo, h.ast_hi)}</td>
                     <td>{range(h.mp, h.mp_lo, h.mp_hi)}</td><td>{h.ts_pct != null ? `${(h.ts_pct * 100).toFixed(1)}%` : DASH}</td></>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {projection.comps.length > 0 && (
        <div className="proj-comps">
          <span className="pbp-subhead" style={{ margin: 0 }}>Most similar at his age</span>
          {projection.comps.map(c => (
            <Link key={c.rank} to={`/players/${c.comp_id}?stat=pts`} className="pill-btn" title={`Similarity ${c.similarity}`}>
              {c.player}{c.hof && <HofBadge />} &rsquo;{String(c.comp_season).slice(2)}
            </Link>
          ))}
        </div>
      )}
      <p className="section-sub" style={{ margin: '12px 0 0' }}>A projection says what usually happens to players like him, not what he&rsquo;ll decide: it can&rsquo;t see injuries, trades, contracts or retirement plans.</p>
    </Panel>
  );
}
