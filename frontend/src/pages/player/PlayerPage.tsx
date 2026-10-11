import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { PlayerDetail, PlayerSeason } from '../../api/types';
import { PlayerSearch } from '../../components/PlayerSearch';
import { ErrorNote, HofBadge, Loading, NoData, Panel, SectionHead } from '../../components/ui';
import { fmtInt, fmtNum, height } from '../../lib/format';
import { FavoriteButton } from '../../components/account';
import { Link } from 'react-router-dom';
import { AdvancedPanel, AwardsTimeline, CareerChart, RolePanel, SimilarPanel } from './panels';
import { ShotProfile } from './ShotProfile';
import { StylePanel } from './StylePanel';
import { PlayoffPanel } from './PlayoffPanel';
import { CareerHighsPanel, GameLogPanel } from './GameLog';
import type { PlayerPlayoffs } from '../../api/types';
import { ProjectionPanel } from './ProjectionPanel';
import { SalaryPanel } from './SalaryPanel';
import type { PlayerProjection } from '../../api/types';

const SUGGESTED = [
  ['jamesle01', 'LeBron James'], ['jordami01', 'Michael Jordan'], ['abdulka01', 'Kareem Abdul-Jabbar'],
  ['birdla01', 'Larry Bird'], ['curryst01', 'Stephen Curry'], ['duncati01', 'Tim Duncan'],
];

export default function PlayerPage() {
  const { playerId } = useParams();
  const navigate = useNavigate();
  const { data: player, error } = useApi<PlayerDetail>(playerId ? `/players/${playerId}` : null);
  const go = (id: string) => navigate(`/players/${id}`);

  return (
    <section className="view active" id="view-players">
      <SectionHead title="Player Explorer">Search any player who has appeared in a box score since the league's founding in 1947.</SectionHead>
      <PlayerSearch onSelect={p => go(p.player_id)} id="player-search" />

      {!playerId && (
        <div className="empty-state" id="player-empty">
          <div className="big">No player selected</div>
          <div>Search above, or try one of these:</div>
          <div style={{ marginTop: 14, display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
            {SUGGESTED.map(([id, name]) => <button key={id} type="button" className="pill-btn" onClick={() => go(id)}>{name}</button>)}
          </div>
        </div>
      )}
      {playerId && error && <ErrorNote error={error} />}
      {playerId && !player && !error && <Loading />}
      {player && player.player_id === playerId && <PlayerCard key={player.player_id} player={player} />}
    </section>
  );
}

const TABS = [
  { key: 'stats', label: 'Stats' }, { key: 'playoffs', label: 'Playoffs' }, { key: 'games', label: 'Game log' },
  { key: 'awards', label: 'Awards' }, { key: 'shooting', label: 'Shooting' }, { key: 'style', label: 'Style & comps' },
  { key: 'projection', label: 'Projection' }, { key: 'contract', label: 'Contract' },
] as const;
type Tab = typeof TABS[number]['key'];

/** The tab in the URL; older links that point into a section (?gl=, ?shot=) open that section's tab. */
function useTab(): [Tab, (t: Tab) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get('tab');
  const implied: Tab = ['gl', 'glt', 'hit'].some(k => params.has(k)) ? 'games' : ['shot', 'shotView'].some(k => params.has(k)) ? 'shooting' : 'stats';
  const tab = (TABS.some(t => t.key === raw) ? raw : implied) as Tab;
  const set = (t: Tab) => {
    const next = new URLSearchParams(params);
    if (t === 'stats') next.delete('tab'); else next.set('tab', t);
    setParams(next, { replace: true });
  };
  return [tab, set];
}

function PlayerCard({ player }: { player: PlayerDetail }) {
  const [tab, setTab] = useTab();
  const { data: seasons } = useApi<PlayerSeason[]>(`/players/${player.player_id}/seasons`);
  const { data: projection } = useApi<PlayerProjection>(`/players/${player.player_id}/projection`);
  const { data: playoffs } = useApi<PlayerPlayoffs>(`/players/${player.player_id}/playoffs`);
  const d = player.draft;
  const draft = d
    ? `Drafted ${d.season} \u00b7 ${d.overall_pick ? `Round ${d.round}, Pick ${d.overall_pick}` : `Round ${d.round}`} \u00b7 ${d.tm}${d.college ? ` \u00b7 ${d.college}` : ''}`
    : player.first_season >= 1950 ? 'Undrafted' : null;
  const stats = [
    ['Games', fmtInt(player.g)], ['Points', fmtInt(player.pts)], ['Rebounds', fmtInt(player.trb)], ['Assists', fmtInt(player.ast)],
    ['PPG', fmtNum(player.ppg)], ['RPG', fmtNum(player.rpg)], ['APG', fmtNum(player.apg)],
    ['All-Star', player.all_star ? `${player.all_star}\u00d7` : '\u2014'], ['Win Shares', fmtNum(player.ws)],
  ];
  return (
    <div className="player-card show" id="player-card">
      <Panel>
        <div className="player-header">
          <div>
            <h1 className="player-name" id="pc-name">{player.player}{player.hof && <HofBadge label="Hall of Fame" />}</h1>
            <div className="player-meta" id="pc-meta">
              {player.pos || '\u2014'} &middot; {player.first_season}&ndash;{player.last_season} ({player.seasons_played} seasons) &middot; {height(player.ht_in_in)}{player.wt ? `, ${player.wt} lb` : ''}
              {draft && <><br />{draft}</>}
            </div>
            {playoffs && playoffs.titles.length > 0 && (
              <div className="titles-line" id="pc-titles"><span className="award-trophy">{'\u{1F3C6}'}</span> <b>{playoffs.titles.length}&times; NBA champion</b>
                <span className="years">{playoffs.titles.map(t => t.season).join(', ')}</span>
                {(playoffs.finals_mvp_seasons ?? []).length > 0 && <span className="years">&middot; <b>{playoffs.finals_mvp_seasons.length}&times; Finals MVP</b> ({playoffs.finals_mvp_seasons.join(', ')})</span>}</div>
            )}
          </div>
          <div className="form-row">
            <FavoriteButton kind="player" refId={player.player_id} label={player.player} />
            <Link className="pill-btn" to={`/lineups/new?p=${player.player_id}`}>Add to a lineup</Link>
          </div>
        </div>
        <div className="player-stat-row" id="pc-stats">
          {stats.map(([l, v]) => <div className="ps-cell" key={l}><div className="v">{v}</div><div className="l">{l}</div></div>)}
        </div>
      </Panel>
      <nav className="tabs player-tabs" id="pc-tabs" role="tablist" aria-label="Player sections">
        {TABS.filter(t => t.key !== 'projection' || projection?.projected).map(t => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} data-tab={t.key}
                  className={`tab-btn ${tab === t.key ? 'active' : ''}`} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </nav>
      <div role="tabpanel" id={`pc-tab-${tab}`}>
        {tab === 'stats' && (<>
          <Panel>{seasons ? <CareerChart seasons={seasons} projection={projection} playoffs={playoffs} /> : <Loading />}</Panel>
          {seasons && <AdvancedPanel player={player} seasons={seasons} />}
        </>)}
        {tab === 'playoffs' && (playoffs
          ? (playoffs.seasons.length ? <PlayoffPanel playoffs={playoffs} /> : <Panel><NoData>{player.player} never played in the playoffs.</NoData></Panel>)
          : <Loading />)}
        {tab === 'games' && (<>
          <CareerHighsPanel playerId={player.player_id} />
          <GameLogPanel playerId={player.player_id} />
        </>)}
        {tab === 'awards' && <AwardsTimeline playerId={player.player_id} />}
        {tab === 'shooting' && (<>
          <ShotProfile playerId={player.player_id} />
          <RolePanel playerId={player.player_id} />
        </>)}
        {tab === 'style' && (<>
          <StylePanel playerId={player.player_id} />
          <SimilarPanel playerId={player.player_id} />
        </>)}
        {tab === 'projection' && (projection ? <ProjectionPanel projection={projection} /> : <Loading />)}
        {tab === 'contract' && <SalaryPanel playerId={player.player_id} />}
      </div>
    </div>
  );
}
