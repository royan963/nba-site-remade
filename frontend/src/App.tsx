import { lazy, Suspense, useEffect } from 'react';
import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { useApi } from './api/hooks';
import type { LiveSeason, Meta } from './api/types';
import { Loading } from './components/ui';
import { fmtInt } from './lib/format';
import { AccountMenu } from './components/account';
import { HeaderSearch } from './components/HeaderSearch';

// Each page is its own bundle, loaded when first visited.
const Overview = lazy(() => import('./pages/Overview'));
const Evolution = lazy(() => import('./pages/Evolution'));
const Leaderboards = lazy(() => import('./pages/Leaderboards'));
const PlayerPage = lazy(() => import('./pages/player/PlayerPage'));
const TeamsPage = lazy(() => import('./pages/teams/TeamsPage'));
const ComparePage = lazy(() => import('./pages/compare/ComparePage'));
const LineupsHome = lazy(() => import('./pages/lineups/LineupsHome'));
const ModelsPage = lazy(() => import('./pages/models/ModelsPage'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const LineupBuilder = lazy(() => import('./pages/lineups/LineupBuilder'));
const LineupView = lazy(() => import('./pages/lineups/LineupView'));
const AccountPage = lazy(() => import('./pages/account/AccountPage'));
const ProfilePage = lazy(() => import('./pages/account/ProfilePage'));
const LoginPage = lazy(() => import('./pages/account/AuthPages').then(m => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import('./pages/account/AuthPages').then(m => ({ default: m.SignupPage })));

const TABS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/evolution', label: 'Era Evolution' },
  { to: '/leaders', label: 'Leaderboards' },
  { to: '/players', label: 'Player Explorer' },
  { to: '/teams', label: 'Team Explorer' },
  { to: '/compare', label: 'Compare' },
  { to: '/lineups', label: 'Lineups' },
  { to: '/models', label: 'Models' },
];

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

export default function App() {
  const { data: meta } = useApi<Meta>('/meta');
  return (
    <div id="app">
      <ScrollToTop />
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="mark">The Shape of the <span className="accent">Game</span></span>
          <span className="tag">NBA History Explorer</span>
        </NavLink>
        <div className="season-span" id="topbar-meta">
          {meta
            ? <>Seasons <b>{meta.first_season}</b> &mdash; <b>{meta.latest_season}</b> &middot; {meta.latest_season - meta.first_season + 1} years &middot; {fmtInt(meta.players)} players</>
            : <>&nbsp;</>}
        </div>
        <HeaderSearch />
        <AccountMenu />
      </header>

      <nav className="tabs" id="main-tabs">
        {TABS.map(t => (
          <NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => `tab-btn ${isActive ? 'active' : ''}`}>
            {t.label}
          </NavLink>
        ))}
      </nav>

      <main>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/evolution" element={<Evolution />} />
            <Route path="/leaders" element={<Leaderboards />} />
            <Route path="/players" element={<PlayerPage />} />
            <Route path="/players/:playerId" element={<PlayerPage />} />
            <Route path="/teams" element={<TeamsPage />} />
            <Route path="/teams/:franchise" element={<TeamsPage />} />
            <Route path="/compare" element={<Navigate to="/compare/players" replace />} />
            <Route path="/compare/:mode/:a?/:b?" element={<ComparePage />} />
            <Route path="/lineups" element={<LineupsHome />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/models" element={<Navigate to="/models/mvp" replace />} />
            <Route path="/models/:model" element={<ModelsPage />} />
            <Route path="/lineups/new" element={<LineupBuilder />} />
            <Route path="/lineups/:lineupId" element={<LineupView />} />
            <Route path="/lineups/:lineupId/edit" element={<LineupBuilder />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/u/:username" element={<ProfilePage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>

      <footer className="footer-note" id="footer-sources">
        <p><b>Data sources</b>{meta && <> &middot; {meta.first_season}&ndash;{meta.latest_season} seasons</>}</p>
        <ul className="footer-sources">
          <li><a href="https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats">NBA Stats (1947-present)</a>: Basketball-Reference
            season stats, advanced stats, awards, All-Star and All-NBA teams, draft and team records for every finished season.</li>
          <li><a href="https://www.kaggle.com/datasets/gonzalogigena/nba-all-time-stats">NBA All Time Stats</a>: Basketball-Reference
            box scores through 2023-24 (game logs, player playoff stats, rosters).</li>
          <li><a href="https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026">Deo Cheng NBA database</a>: playoff series and
            champions, game logs and play-by-play from 2024-25, the newest award voting, salaries and contracts.</li>
          <li><a href="https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores">eoinamoore NBA box scores</a>{' '}
            (updated daily): the newest games, play-in and NBA Cup tags, this season&rsquo;s rookies, and the season in progress.</li>
        </ul>
        <LiveSeasonFooter live={meta?.live_season} />
        <p>ABA seasons excluded from league averages &middot; regular season unless noted &middot; seasons are named by the year
          they end (2027 = 2026-27) &middot; <a href="/docs">API docs</a></p>
      </footer>
    </div>
  );
}

/** How the season in progress is built, when its stats come from the daily box scores rather than the main dataset. */
function LiveSeasonFooter({ live }: { live?: LiveSeason | null }) {
  if (!live || !live.in_progress) return null;
  const name = `${live.season - 1}-${String(live.season).slice(2)}`;
  if (live.source !== 'box_scores' || !live.through) {
    return <p id="footer-live-season">The {name} season is in progress; its numbers come from the main dataset and change as games are played.</p>;
  }
  const through = new Date(`${live.through.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  return (
    <p id="footer-live-season">
      <b>{name} season in progress:</b> rebuilt every day from all {Math.round(live.games)} box scores through {through}, because the main
      dataset runs behind. Per-game stats, shooting, PER, TS%, usage, team records, ratings and SRS use Basketball-Reference&rsquo;s
      formulas; Win Shares, BPM and VORP are estimates fit on past seasons. The MVP and title predictors update daily and keep
      their preseason picks for comparison; season records are marked &ldquo;in progress&rdquo; until the season ends.
    </p>
  );
}

function NotFound() {
  return (
    <section className="view active">
      <div className="empty-state">
        <div className="big">Page not found</div>
        <div><NavLink to="/">Back to the overview</NavLink></div>
      </div>
    </section>
  );
}
