import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { ChampionModel, ChampionSeason } from '../../api/types';
import { ErrorNote, Loading, NoData, Panel, SectionHead } from '../../components/ui';
import { DASH, fmtNum, fmtSigned } from '../../lib/format';
import { useQueryParam } from '../../lib/useQuery';
import { slugify } from '../teams/geo';

const pct = (v: number | null | undefined, d = 0) => (v == null ? DASH : `${(v * 100).toFixed(d)}%`);
const chance = (v: number) => (v >= 0.995 ? '>99%' : v > 0 && v < 0.005 ? '<1%' : pct(v));

export function ChampionPage() {
  const { data: model, error } = useApi<ChampionModel>('/models/champion');
  const [seasonRaw, setSeason] = useQueryParam('season', '');
  if (error) return <ErrorNote error={error} />;
  if (!model) return <Loading />;
  const current = model.preseason?.season ?? model.latest_season;
  const season = model.seasons.includes(parseInt(seasonRaw, 10)) ? parseInt(seasonRaw, 10) : current;
  return (
    <div id="champion-page">
      <Race model={model} season={season} onSeason={v => setSeason(v === current ? '' : String(v))} />
      <ModelCard model={model} onSeason={v => setSeason(String(v))} />
    </div>
  );
}

function Race({ model, season, onSeason }: { model: ChampionModel; season: number; onSeason: (s: number) => void }) {
  const { data, error } = useApi<ChampionSeason>(`/models/champion/${season}`);
  const pre = data?.kind === 'preseason' ? model.preseason : null;
  const decided = data?.kind === 'backtest';
  const champ = data?.teams.find(t => t.champion);
  const top = data?.teams[0];
  return (
    <Panel id="champion-race">
      <div className="player-header">
        <div>
          <SectionHead title={`${season} title odds${pre ? ' (preseason)' : ''}`} small>
            {pre
              ? `Before any ${season} games, from each team’s ${pre.base_season} season. Tested on every season from ${pre.season - pre.metrics.seasons} on, the favorite won the title ${pct(pre.metrics.top1)} of the time and the champion was in its top 3 ${pct(pre.metrics.top3)} of the time (last season’s best point differential: ${pct(pre.metrics.baseline_top1)}).`
              : decided
              ? 'Backtest: odds after the regular season, from a model trained on every other season, so it never saw how this one ended.'
              : `A true prediction: the ${season} playoffs aren’t in the data yet. The model was trained on every season through ${model.metrics.trained_through}.`}
          </SectionHead>
        </div>
        <select id="champion-season" value={season} onChange={e => onSeason(parseInt(e.target.value, 10))} aria-label="Season">
          {model.seasons.map(s => <option key={s} value={s}>{s}{s === model.preseason?.season ? ' (preseason)' : s === model.latest_season && !model.latest_has_champion ? ' (prediction)' : ''}</option>)}
        </select>
      </div>
      {error && <ErrorNote error={error} />}
      {!data && !error && <Loading />}
      {data && decided && champ && top && (
        <div className={`mvp-verdict ${top.champion ? 'hit' : 'miss'}`} id="champion-verdict">
          {top.champion
            ? <>The favorite won it all: <b>{champ.team_name}</b> ({pct(champ.win_prob)}).</>
            : <>The model favored <b>{top.team_name}</b> ({pct(top.win_prob)}); <b>{champ.team_name}</b> won it (model rank #{champ.rank}, {pct(champ.win_prob)}).</>}
        </div>
      )}
      {data && pre && (
        <p className="section-sub" id="champion-preseason-note" style={{ margin: '0 0 10px' }}>
          Records, ratings and best players are from {data.stats_season}, so offseason trades, signings and injuries aren&rsquo;t reflected. A year out, titles are hard to call: the model mostly follows point differential and the best player&rsquo;s impact.
        </p>
      )}
      {data && (
        <div className="table-scroll">
          <table className="lb-table mvp-table">
            <thead>
              <tr>
                <th>#</th><th>Team</th><th>W-L</th><th>SRS</th><th>Net rtg</th><th title="Most VORP on the roster">Top player</th><th title="Best Box Plus/Minus on the roster (1,000+ minutes), a model input">Best BPM</th>
                <th>Title chance</th>{decided && <th>What happened</th>}
              </tr>
            </thead>
            <tbody id="champion-tbody">
              {data.teams.map(t => (
                <tr key={t.franchise} className={t.champion ? 'mvp-winner' : ''}>
                  <td className="rank-cell">{t.rank}</td>
                  <td className="name-cell">
                    <Link to={`/teams/${slugify(t.franchise)}`}>{t.team_name ?? t.franchise}</Link>
                    {t.champion && <span className="mvp-trophy" title="Champion">{'\u{1F3C6}'}</span>}
                  </td>
                  <td>{t.w != null && t.l != null ? `${t.w}-${t.l}` : DASH}</td>
                  <td>{fmtSigned(t.srs)}</td>
                  <td>{fmtSigned(t.net)}</td>
                  <td>{t.star_id ? <Link to={`/players/${t.star_id}`} className="name-link">{t.star ?? t.star_id}</Link> : DASH}</td>
                  <td>{fmtSigned(t.top_bpm)}</td>
                  <td>
                    <div className="mvp-share"><div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${Math.min(100, t.win_prob * 100)}%` }} /></div>
                      <span>{chance(t.win_prob)}</span></div>
                  </td>
                  {decided && <td>{t.champion ? <b>Champion</b> : t.result ?? DASH}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Weights({ weights }: { weights: ChampionModel['weights'] }) {
  const max = Math.max(...weights.map(w => Math.abs(w.weight)), 0.0001);
  return (
    <>
      {weights.map(w => (
        <div className="lineup-bar importance-bar" key={w.feature}>
          <span className="lineup-bar-label" style={{ textTransform: 'none' }}>{w.label}</span>
          <div className="position-bar-track"><div className="position-bar-fill" style={{ width: `${(Math.abs(w.weight) / max) * 100}%` }} /></div>
          <span className="lineup-bar-value">{fmtNum(w.weight, 2)}</span>
        </div>
      ))}
    </>
  );
}

function ModelCard({ model, onSeason }: { model: ChampionModel; onSeason: (s: number) => void }) {
  const m = model.metrics;
  const pre = model.preseason;
  return (
    <>
      <div className="panel-row">
        <Panel id="champion-accuracy">
          <SectionHead title="How accurate is it?" small>After the regular season, every season from {m.trained_through - m.seasons + 1} to {m.trained_through} predicted by a model that never saw it.</SectionHead>
          <div className="player-stat-row">
            {[['Favorite won the title', pct(m.top1), `${Math.round(m.top1 * m.seasons)} of ${m.seasons} seasons`],
              ['Champion in its top 3', pct(m.top3), ''],
              ['Baseline: best point differential', pct(m.baseline_top1), 'simplest rule'],
              ...(pre ? [['Preseason favorite won', pct(pre.metrics.top1), `vs ${pct(pre.metrics.baseline_top1)} for last season’s best SRS`]] : [])].map(([l, v, sub]) => (
              <div className="ps-cell" key={l}><div className="v">{v}</div><div className="l">{l}{sub && ` · ${sub}`}</div></div>
            ))}
          </div>
        </Panel>
        <Panel id="champion-weights">
          <SectionHead title="What the model weighs" small>Logistic regression weights on standardized inputs: bigger means more influence on a team&rsquo;s title chances.</SectionHead>
          <Weights weights={model.weights} />
          {pre && (
            <>
              <div className="pbp-subhead" style={{ marginTop: 14 }}>Preseason model</div>
              <Weights weights={pre.weights} />
            </>
          )}
        </Panel>
      </div>
      <Panel id="champion-misses">
        <SectionHead title={`The ${model.misses.length} seasons the favorite didn’t win`} small>Upsets, injuries, and teams that peaked in the playoffs.</SectionHead>
        {model.misses.length === 0 ? <NoData>None.</NoData> : (
          <div className="mvp-misses">
            {[...model.misses].reverse().map(x => (
              <button key={x.season} type="button" className="saved-row link-row mvp-miss champion-miss" onClick={() => { onSeason(x.season); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>
                <span className="awards-season-tag">{x.season}</span>
                <span>Model: {x.predicted} &middot; Champion: <b>{x.actual}</b></span>
              </button>
            ))}
          </div>
        )}
      </Panel>
      <details className="lineup-notes">
        <summary>How it works</summary>
        <p>A logistic regression learns which teams win titles from each season&rsquo;s point differential (SRS) and record against the league, the combined VORP of its three best players, its best player&rsquo;s Box Plus/Minus, and how far it went in the playoffs the year before. Bigger models did no better: there are only about 77 champions to learn from.</p>
        <p>Chances are each team&rsquo;s score as a share of the whole league&rsquo;s, sharpened by a power fit on the backtest, so they match how often favorites really won. The preseason odds come from a second model that learned how a team&rsquo;s season carries over to the next year&rsquo;s title, using only last season&rsquo;s point differential and best player. It can&rsquo;t see trades, free agency, injuries or the draft.</p>
      </details>
    </>
  );
}
