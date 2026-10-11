import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { MvpModel, MvpSeason } from '../../api/types';
import { ErrorNote, HofBadge, Loading, NoData, Panel, SectionHead } from '../../components/ui';
import { DASH, fmtNum, fmtSigned } from '../../lib/format';
import { useQueryParam } from '../../lib/useQuery';

const pct = (v: number | null | undefined, d = 0) => (v == null ? DASH : `${(v * 100).toFixed(d)}%`);
const chance = (v: number) => (v >= 0.995 ? '>99%' : v > 0 && v < 0.005 ? '<1%' : pct(v));

export function MvpPage() {
  const { data: model, error } = useApi<MvpModel>('/models/mvp');
  const [seasonRaw, setSeason] = useQueryParam('season', '');
  if (error) return <ErrorNote error={error} />;
  if (!model) return <Loading />;
  const current = model.preseason?.season ?? model.latest_season;     // the upcoming season once the last vote is in
  const season = model.seasons.includes(parseInt(seasonRaw, 10)) ? parseInt(seasonRaw, 10) : current;
  return (
    <div id="mvp-page">
      <Race model={model} season={season} onSeason={v => setSeason(v === current ? '' : String(v))} />
      <ModelCard model={model} onSeason={v => setSeason(String(v))} />
    </div>
  );
}

function Race({ model, season, onSeason }: { model: MvpModel; season: number; onSeason: (s: number) => void }) {
  const { data, error } = useApi<MvpSeason>(`/models/mvp/${season}`);
  const prediction = data?.kind === 'prediction' || data?.kind === 'preseason';
  const pre = data?.kind === 'preseason' ? model.preseason : null;
  const winner = data?.candidates.find(c => c.winner);
  const top = data?.candidates[0];
  return (
    <Panel id="mvp-race">
      <div className="player-header">
        <div>
          <SectionHead title={`${season} MVP race${pre ? ' (preseason)' : ''}`} small>
            {pre
              ? `A preseason prediction, before any ${season} games: a second model learned how each season’s stats and voting carry over to the next MVP vote. Tested on every season from ${pre.season - pre.metrics.seasons} on, it picked the eventual MVP ${pct(pre.metrics.top1)} of the time and had him in its top 3 ${pct(pre.metrics.top3)} of the time (last season’s top vote-getter: ${pct(pre.metrics.baseline_top1)}).`
              : prediction
              ? `A true prediction: ${season} voting isn\u2019t in the dataset yet. The model was trained on every season from 1956 to ${model.metrics.trained_through}.`
              : `Backtest: this season was predicted by a model trained on every other season, so it never saw this vote.`}
          </SectionHead>
        </div>
        <select id="mvp-season" value={season} onChange={e => onSeason(parseInt(e.target.value, 10))} aria-label="Season">
          {model.seasons.map(s => <option key={s} value={s}>{s}{s === model.preseason?.season ? ' (preseason)' : s === model.latest_season && !model.latest_has_votes ? ' (prediction)' : ''}</option>)}
        </select>
      </div>
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      {data && !prediction && winner && top && (
        <div className={`mvp-verdict ${top.winner ? 'hit' : 'miss'}`} id="mvp-verdict">
          {top.winner
            ? <>The model picked the winner: <b>{winner.player}</b>.</>
            : <>The model picked <b>{top.player}</b>; voters chose <b>{winner.player}</b> (model rank #{winner.rank}).</>}
        </div>
      )}
      {data && pre && (
        <p className="section-sub" id="mvp-preseason-note" style={{ margin: '0 0 10px' }}>
          Stats, team and games are from the {data.stats_season} season, so offseason trades and injuries aren&rsquo;t reflected. It uses: {pre.metrics.features.join(', ')}.
        </p>
      )}
      {data && (
        <div className="table-scroll">
          <table className="lb-table mvp-table">
            <thead>
              <tr>
                <th>#</th><th>Player</th><th>Team</th><th>GP</th><th>PTS</th><th>REB</th><th>AST</th><th>PER</th><th>WS</th><th>BPM</th>
                <th>Predicted vote share</th><th>{prediction ? 'Chance to win' : 'Model\u2019s chance'}</th>
                {!prediction && <><th>Actual share</th><th>Actual finish</th></>}
              </tr>
            </thead>
            <tbody id="mvp-tbody">
              {data.candidates.map(c => (
                <tr key={c.player_id} className={c.winner ? 'mvp-winner' : ''}>
                  <td className="rank-cell">{c.rank}</td>
                  <td className="name-cell">
                    <Link to={`/players/${c.player_id}`}>{c.player}</Link>{c.hof && <HofBadge />}{c.winner && <span className="mvp-trophy" title="Won MVP">{'\u{1F3C6}'}</span>}
                    {c.needs_exception && <div className="mvp-flag">{c.g} games: under {model.games_rule.min}, eligible only through an NBA exception</div>}
                  </td>
                  <td>{c.team ?? DASH}{c.win_pct != null && <span className="similar-meta"> {pct(c.win_pct)}</span>}</td>
                  <td>{c.g ?? DASH}</td>
                  <td>{fmtNum(c.pts)}</td><td>{fmtNum(c.trb)}</td><td>{fmtNum(c.ast)}</td>
                  <td>{fmtNum(c.per)}</td><td>{fmtNum(c.ws)}</td><td>{fmtSigned(c.bpm)}</td>
                  <td>
                    <div className="mvp-share"><div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${Math.min(100, c.predicted_share * 100)}%` }} /></div>
                      <span>{pct(c.predicted_share)}</span></div>
                  </td>
                  <td>{chance(c.win_prob)}</td>
                  {!prediction && <><td>{pct(c.actual_share)}</td><td>{c.actual_rank ? `#${c.actual_rank}` : 'no votes'}</td></>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && !pre && model.games_rule_season <= season && (
        <p className="section-sub" style={{ marginTop: 12, marginBottom: 0 }}>
          From {model.games_rule_season} on, MVP candidates need {model.games_rule.min} games. Players under {model.games_rule.hard_min} are left out; the exceptions that count some shorter games aren&rsquo;t in this data.
        </p>
      )}
    </Panel>
  );
}

function ModelCard({ model, onSeason }: { model: MvpModel; onSeason: (s: number) => void }) {
  const m = model.metrics;
  const maxImp = Math.max(...model.importances.map(i => i.importance), 0.0001);
  return (
    <>
      <div className="panel-row">
        <Panel id="mvp-accuracy">
          <SectionHead title="How accurate is it?" small>Every season from 1956 to {m.trained_through} predicted by a model that never saw that season&rsquo;s vote.</SectionHead>
          <div className="player-stat-row">
            {[['Picked the MVP', pct(m.top1), `${Math.round(m.top1 * m.seasons)} of ${m.seasons} seasons`],
              ['Winner in its top 3', pct(m.top3), ''],
              ['Baseline: Win Shares leader', pct(m.baseline_top1), 'simplest rule'],
              ['Avg. rank of real MVP', m.mean_winner_rank.toFixed(2), '1 = always first']].map(([l, v, sub]) => (
              <div className="ps-cell" key={l}><div className="v">{v}</div><div className="l">{l}{sub && ` \u00b7 ${sub}`}</div></div>
            ))}
          </div>
        </Panel>
        <Panel id="mvp-importance">
          <SectionHead title="What the model weighs most" small>How much accuracy drops when each input is scrambled (permutation importance).</SectionHead>
          {model.importances.slice(0, 10).map(i => (
            <div className="lineup-bar importance-bar" key={i.feature}>
              <span className="lineup-bar-label" style={{ textTransform: 'none' }}>{i.label}</span>
              <div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${Math.max(0, i.importance / maxImp) * 100}%` }} /></div>
              <span className="lineup-bar-value">{i.importance.toFixed(3)}</span>
            </div>
          ))}
        </Panel>
      </div>
      <Panel id="mvp-misses">
        <SectionHead title={`The ${model.misses.length} seasons it got wrong`} small>Often famous debates: the stats pointed one way and voters went another.</SectionHead>
        {model.misses.length === 0 ? <NoData>None.</NoData> : (
          <div className="mvp-misses">
            {[...model.misses].reverse().map(x => (
              <button key={x.season} type="button" className="saved-row link-row mvp-miss" onClick={() => { onSeason(x.season); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
                <span className="awards-season-tag">{x.season}</span>
                <span>Model: {x.predicted_name} &middot; Voters: <b>{x.actual_name}</b></span>
              </button>
            ))}
          </div>
        )}
      </Panel>
      <details className="lineup-notes">
        <summary>How it works</summary>
        <p>A gradient-boosted tree model (scikit-learn) learns each player&rsquo;s share of the MVP vote from: box-score and advanced stats (PER, Win Shares, BPM, VORP, true shooting, usage), his team&rsquo;s record and league rank, how he ranks against the rest of that season (MVP is decided against the field), and how many MVPs he&rsquo;d already won (voter fatigue). Win chances turn predicted vote shares into probabilities, calibrated so they match how often the favorite really won.</p>
        <p>It&rsquo;s a model of how voters behave, not of who was truly most valuable, and it can&rsquo;t see narratives, injuries or the eye test, which is exactly where its misses tend to happen.</p>
      </details>
    </>
  );
}
