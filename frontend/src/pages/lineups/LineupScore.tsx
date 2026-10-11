import { Link } from 'react-router-dom';
import type { LineupScore as Score } from '../../api/types';
import { HofBadge, NoData } from '../../components/ui';
import { fmtNum, fmtSigned } from '../../lib/format';

const RATING_LABELS: [keyof Score['players'][number]['ratings'], string][] = [
  ['scoring', 'Scoring'], ['playmaking', 'Playmaking'], ['rebounding', 'Rebounding'], ['defense', 'Defense'],
  ['efficiency', 'Efficiency'], ['spacing', 'Spacing'],
];

function Bar({ label, value, big }: { label: string; value: number | null; big?: boolean }) {
  return (
    <div className={`lineup-bar ${big ? 'big' : ''}`}>
      <span className="lineup-bar-label">{label}</span>
      <div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${value ?? 0}%` }} /></div>
      <span className="lineup-bar-value">{value == null ? '\u2014' : Math.round(value)}</span>
    </div>
  );
}

/** Overall score, category breakdown, fit notes and per-player ratings. */
export function LineupScoreView({ score }: { score: Score }) {
  return (
    <div id="lineup-score">
      <div className="lineup-summary">
        <div className="lineup-overall" id="lineup-overall">
          <span className="lineup-overall-value">{score.overall ?? '\u2014'}</span>
          <span className="lineup-overall-label">{score.complete ? score.grade : `Add ${5 - score.players.length} more`}</span>
        </div>
        <div className="lineup-summary-text">
          {score.complete && score.real_percentile != null
            ? <>Better than <b>{Math.round(score.real_percentile)}%</b> of real NBA starting fives since 1951-52 (each team-season&rsquo;s five highest-minute players), using the same scoring.</>
            : <>Pick five players to get an overall score. Category scores update as you go.</>}
        </div>
      </div>

      <div className="lineup-categories">
        {score.categories.map(c => <Bar key={c.key} label={c.label} value={c.key === 'fit' && !score.complete ? null : c.score} big={c.key === 'talent'} />)}
      </div>

      {score.fit_notes.length > 0 && (
        <ul className="lineup-fit-notes">{score.fit_notes.map(n => <li key={n}>{n}</li>)}</ul>
      )}

      <div className="lineup-players">
        {score.players.map(p => (
          <div className="lineup-player-card" key={p.player_id}>
            <div className="lineup-player-head">
              <Link to={`/players/${p.player_id}`} className="name-link">{p.player}</Link>{p.hof && <HofBadge />}
              <span className="lineup-player-rating" title="Talent rating: percentile among all qualified seasons">{p.rating == null ? '\u2014' : Math.round(p.rating)}</span>
            </div>
            <div className="similar-meta">{p.season} &middot; {p.teams.join(' / ')} &middot; {p.pos || '\u2014'}{p.age ? ` \u00b7 age ${p.age}` : ''}</div>
            <div className="similar-meta">{fmtNum(p.pts)} pts &middot; {fmtNum(p.trb)} reb &middot; {fmtNum(p.ast)} ast{p.bpm != null && <> &middot; {fmtSigned(p.bpm)} BPM</>}</div>
            {p.tags.length > 0 && <div className="lineup-tags">{p.tags.map(t => <span key={t} className="award-pill won">{t}</span>)}</div>}
            <div className="lineup-mini-bars">{RATING_LABELS.map(([k, l]) => <Bar key={k} label={l} value={p.ratings[k]} />)}</div>
          </div>
        ))}
        {score.players.length === 0 && <NoData>No players yet.</NoData>}
      </div>

      {score.notes.length > 0 && (
        <details className="lineup-notes">
          <summary>About the data ({score.notes.length})</summary>
          <ul>{score.notes.map(n => <li key={n}>{n}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

export function HowItWorks() {
  return (
    <details className="lineup-notes" id="lineup-how">
      <summary>How the score works</summary>
      <p>Every player-season is compared with its own league, so a 1962 season and a 2024 season are rated on the same scale. Each player gets percentiles against all qualified seasons since 1947 (40+ games and, once minutes were recorded, 1,200+ minutes): <b>talent</b> from impact stats (Box Plus/Minus, Win Shares per 48, PER), plus scoring, playmaking, rebounding, defense, efficiency and three-point spacing rates relative to that season&rsquo;s league.</p>
      <p>The lineup score is mostly talent, plus how well the skills cover each other, and a <b>fit</b> score that docks lineups with too much ball-dominance (combined usage), no big man, no guard, or no outside shooting. It&rsquo;s graded against every real starting five since 1951-52. It&rsquo;s for fun and debate, not a prediction.</p>
    </details>
  );
}
