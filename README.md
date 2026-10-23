# The Shape of the Game — NBA History Explorer

[![Tests](https://github.com/royan963/nba-site-remade/actions/workflows/tests.yml/badge.svg)](https://github.com/royan963/nba-site-remade/actions/workflows/tests.yml)

An interactive dashboard exploring 80 seasons of NBA history (1947–2026): league-wide trends, player and team stats, a map of franchise locations and relocations, and side-by-side comparisons.

This repository, `nba-site-remade`, is the remade version of [Nba_History](https://github.com/royan963/Nba_History).

**Live site:** https://nba-history.onrender.com/ — the full app (React + API) with every feature below, deployed on Render from this repo. It's on Render's free plan, so the first visit after a quiet spell can take about a minute while it wakes up.

Other versions:

- **Static build** (no server, fewer features): https://royan963.github.io/nba-site-remade/, served by GitHub Pages from `index.html` on `main`.
- **Original site:** https://royan963.github.io/Nba_History/

```bash
git clone https://github.com/royan963/nba-site-remade.git
cd nba-site-remade
```

It comes in two versions built from the same data:

- **Full stack** — a **React + TypeScript** app (Vite, React Router) on a **FastAPI** REST API over **PostgreSQL** (or SQLite). Every view has its own URL, so any player, team, comparison or chart setting is a shareable link. The first load is about 130 KB gzipped; everything else is fetched from the API as you go.
- **Static** — `index.html`, one self-contained file with all data embedded and no server. This is what GitHub Pages serves today.

```
 Kaggle CSVs ─► scripts/prep_data.py ─► data/*.json ─┬─► build.py ─────────────► index.html (static, GitHub Pages)
                                                     │
                                                     └─► backend/etl/load_db.py ─► PostgreSQL / SQLite
                                                                                        │
                    browser ◄─ React app (frontend/dist) ◄─ FastAPI /api/v1/... ◄───────┘
```

## Features

- **Overview** — league scoring, pace and shooting trends with a scrubbable season timeline.
- **Era Evolution** — how the game changed decade by decade (3-point rate, pace, ratings).
- **Leaderboards** — sortable career leaders (including Win Shares, VORP and All-Star selections), filterable by era.
- **Player Explorer** — organized into tabs (Stats, Playoffs, Game log, Awards, Shooting, Style & comps, Projection, Contract) under a header with the career line; the open tab is in the URL (`?tab=awards`), and older links to a game log or shot chart open the right tab. draft info, career trajectory charts (box score and advanced: PER, TS%, usage, Win Shares, BPM, VORP), an advanced-metrics summary, All-Star/awards/All-NBA timeline, an interactive shot-zone court map with league-average comparison, position mix and play-by-play stats.
- **Similar Players** — each player's closest stylistic matches across all eras, matched on a league-relative career stat fingerprint, how he scores (free throws per shot, three-point accuracy, and from 1996-97 on, assisted-shot share and shot locations), and his mix of playing styles (so players who changed roles, like Brook Lopez becoming a stretch big, match others who made the same change, and players with similar box scores but opposite scoring styles, like Curry and Harden, don't count as twins), with a one-click comparison. Stats an older player never had recorded count as a partial mismatch, so old-era matches aren't inflated.
- **Salaries and contracts** — every player's pay by season since 1996-97 with his league rank, career earnings and current contract through 2030-31 (player and team options, guaranteed money, notes such as waivers and extensions), and every team's payroll history, current salary sheet and committed money for future seasons, measured against the salary cap, luxury tax and aprons. Contracts come from Basketball-Reference's team pages (each team's sheet adds up exactly to its official payroll, including money owed to waived players); past salaries are matched to players by name, with every match made under a different name checked by hand.
- **Team Explorer** — U.S./Canada map of every franchise by season, with relocation paths, plus season-by-season rosters.
- **Accounts** — sign up with email and password to favorite players and teams, save comparisons with notes, and get a public profile page (`/u/<username>`) showing what you've shared.
- **All-Time Lineups** — pick any five player-seasons from any era. Every season is rated against its own league; the lineup is scored on talent, scoring, playmaking, rebounding, defense, spacing, efficiency and fit (combined usage, having a big and a guard), then graded against every real NBA starting five since 1951-52. Lineups can be saved, made public, shared, and remixed; unsaved lineups are shareable links too.
- **Models: MVP Predictor** — a gradient-boosted model trained on every MVP vote since 1956 predicts each season's race from stats, team success, standing against that season's field and prior MVPs. Tested leave-one-season-out (each season predicted by a model that never saw it): it picks the real MVP in 63% of seasons and has him in its top 3 in 93%, against 55% for "pick the Win Shares leader." The page shows the current race, any past race next to the real vote, what the model weighs, and every season it got wrong. Between seasons it shows a **preseason race** for the season ahead, from a second model that learned how one season's stats and voting carry over to the next vote (age, last season's vote share, VORP, BPM, Win Shares, team win %): tested the same way, it picked the eventual MVP in 37% of seasons a year out (top 3: 71%), against 27% for "last season's top vote-getter", and its win chances are calibrated so a 30% favorite wins about 30% of the time.
- **Models: Champion Predictor** — every team's title chances each season since 1950. After the regular season, a logistic regression on point differential (SRS), record, the top three players' VORP, the best player's BPM and last year's playoff run picks the champion in 52% of seasons (top 3: 83%), against 48% for "best point differential", tested leave-one-season-out. Between seasons it shows preseason odds for the season ahead from last season's point differential and best player (38% vs 36% for last season's best SRS: a year out, titles are hard to call). Win chances are calibrated against the backtest, and the page lists every season the favorite didn't win.
- **Models: Player Archetypes** — every player-season since 1951-52 sorted into one of 10 playing styles (star creator, spot-up shooter, rim protector, stretch big…) by k-means clustering on league-relative style stats, including three-point tendency measured against players of the same height. A stacked chart shows how the league's minutes shifted between roles: spot-up shooters went from 3% of minutes in the 1980s to 15% in the 2020s while rebounding forwards fell from 18% to 9%. Most players blend roles, so every season (and career) gets a style mix, e.g. Brook Lopez: stretch big 51%, scoring big 37%; player pages show the mix over his career and season by season.
- **Models: Career Projections** — each current player's next three seasons, from how the most similar players at the same age actually developed (nearest neighbors on league-relative per-36 production and minutes, this season and last). Shows a projection with a 60% range, the chance he plays each season, and his closest comparables; the player's career chart extends into the projection. Backtested on 2005-2023 using only comparables whose futures were already known: it beats both "same as last season" and the league aging curve at every horizon (3 seasons out: 3.16 vs 3.77 and 3.36 points per game of error), and its 60% range holds 62-63% of real outcomes.
- **Ask the stats (natural-language search)** — questions about a player ("how many rings does lebron have", "how tall is wembanyama", "lebron mvps", "sga salary") get a direct answer or a player card, with names, nicknames and well-known surnames recognized ("LeBron", "SGA", "Jordan"); two players ("curry vs harden") get a side-by-side and a link to the full comparison; it also reads playoff questions ("top 10 scorers in playoff history"), single games ("most points in a playoff game", "james harden 50 point games"), championships, height, age ("youngest MVPs"), defense, salaries and every season award, and points questions about the future to the MVP and champion predictors. The header box suggests the question and matching players as you type. type a question like "best rebounding guards of the 90s", "players who averaged 25 and 10 since 2010", "50/40/90 seasons", "Celtics leading scorers in the 80s" or "stretch bigs of the 2010s" in the header search box. A rule-based parser (no AI service or API key; deterministic) reads stats, positions, playing styles, eras, ages, teams, statlines, honors and seasons-vs-careers, shows its reading as removable filter chips, and applies sensible minimums so small samples don't top the list. A player's name finds the player.
- **Game by game** — every game since 1946-47 (73,000 games, 1.48 million player-games): each player's game log by season, career highs (Wilt's 100, Kobe's 81) with 30/40/50-point, double-double and triple-double counts, and real head-to-head on the Compare pages: two franchises' all-time record, playoff series and recent games; two players' records and averages in the games they faced each other. Coverage: all seasons through 2023-24; 2024-25 and 2025-26 regular seasons and the 2025-26 playoffs; the 2024-25 playoffs aren't in any available dataset and the pages say so.
- **Playoffs and championships** — every playoff series since 1947 (908 of them) and all 80 champions through 2026, with runners-up and Finals MVPs (1969 on). Player pages show rings (Jordan 6×, Russell 11×) and Finals MVPs, a season-by-season playoff table with each year's result, and a Regular season / Playoffs toggle on the career chart. Team pages show championships, Finals trips and series record; Team Explorer has a Champions view; Leaderboards switch to career playoff totals; team comparisons add championships. Built from two sources and cross-checked: 17 of 17 title counts I tested match, Jordan's 5,987 playoff points and 33.4 average match exactly, rings agree with the official counts for 639 of 643 players, and all 37 Finals MVPs match official totals. Player playoff stats run through 2026: through 2024 from box scores; for 2026 from series-by-series totals (which have minutes) plus the game logs for the players those totals leave out, with every team's player points adding up to its real total; for 2025, which has no box scores anywhere, from series totals alone, so some players are missing that year and the pages say so.
- **Compare** — players (aligned by calendar year, age, or experience) and teams (full history or a chosen season, including awards and All-Stars on each roster). Player comparisons can switch between a season snapshot and an optional career overlay chart, and between three stat bases:
  - *Raw box score* — as recorded.
  - *Per 100 possessions* — removes pace differences (1973-74 onward).
  - *Era-adjusted* — each stat relative to that season's league average (100 = average), so a 1962 season and a 2024 season can be read on the same scale.

## Running the full stack

**Quickest (SQLite, no database server):**

```bash
pip install -r backend/requirements.txt
(cd frontend && npm install && npm run build)   # builds frontend/dist
python3 -m uvicorn backend.app.main:app --reload
```

On first start the server loads `data/*.json` into the database by itself (a few seconds), and reloads the stats whenever `data/` changes; accounts are never touched. (`python3 -m backend.etl.load_db` does the same by hand; set `AUTO_LOAD_DATA=0` to turn the automatic load off.) Using `python3 -m pip` and `python3 -m uvicorn` makes sure both run with the same Python, which matters if you have more than one installed (e.g. Anaconda plus python.org).

Open http://localhost:8000 for the site and http://localhost:8000/docs for interactive API docs.

**Frontend development:** run the API as above, then `cd frontend && npm run dev` and open http://localhost:5173. Vite hot-reloads your changes and forwards `/api` calls to the server on port 8000.

**With PostgreSQL:** set `DATABASE_URL` before loading and serving:

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/nba
python3 -m uvicorn backend.app.main:app        # loads the stats on first start
```

**With Docker:** `docker compose up --build` starts PostgreSQL, loads it and serves the app on port 8000. `docker build -t nba-history . && docker run -p 8000:8000 nba-history` runs a single container with SQLite built in.

### Shareable URLs

Every view and setting lives in the URL, so the address bar is always a link to exactly what's on screen, and Back/Forward work as you'd expect.

| URL | Shows |
|---|---|
| `/players/curryst01?stat=ts_pct&shot=2016&shotView=bars` | A player, with the career chart on TS% and the 2016 shot profile as bars |
| `/teams?season=1950` | The league map in 1950 |
| `/teams/boston-celtics?roster=1986` | A franchise's history and its 1986 roster |
| `/leaders?stat=ws&era=1990-2009` | A filtered leaderboard |
| `/compare/players/jamesle01/jordami01?align=age&basis=index&pos=27` | Two careers at the same age, era-adjusted |
| `/compare/players/jamesle01/jordami01?view=overlay&stat=i_pts` | The career overlay chart |
| `/compare/teams/boston-celtics/los-angeles-lakers?scope=season&sa=2008&sb=2008` | Two team-seasons side by side |
| `/lineups/new?p=jordami01:1996,pippesc01:1996,rodmade01` | An unsaved lineup (season optional: defaults to the player's best) |
| `/lineups/12`, `/u/royan` | A shared lineup; a public profile |

### API

All endpoints are `GET`, JSON and versioned under `/api/v1`. Full reference with try-it-out at `/docs`.

| Endpoint | What it returns |
|---|---|
| `/players?q=jokic` | Search by name (accent-insensitive), best scorers first |
| `/players/{id}` | Career totals, draft, All-Star seasons |
| `/players/{id}/seasons` | Per-game stats by season, with advanced metrics and per-100 merged in |
| `/players/{id}/shooting`, `/play-by-play` | Shot zones, position mix and on/off stats (1997+) |
| `/players/{id}/honors` | Awards and voting, All-NBA/All-Defense teams, All-Star selections |
| `/players/{id}/similar?era=same` | Closest stylistic matches and the player's style fingerprint |
| `/players/{id}/bundle` | Everything above in one request |
| `/players/index` | Every player's career line in compact form |
| `/leaders?stat=ws&era=1990-2009` | Career leaderboard for any stat, optionally by era |
| `/compare/players?a=&b=&align=age&basis=index` | Two careers aligned by experience, age or season, in raw, per-100 or era-adjusted terms |
| `/teams`, `/teams/{franchise}/seasons` | Franchise lineages and season-by-season records |
| `/teams/{franchise}/roster/{season}` | A season's roster with per-game stats |
| `/teams/{franchise}/honors?season=` | Awards, All-NBA teams and All-Stars won by that roster |
| `/teams/geo` | Every team-season with location and colors (for the map) |
| `/league/trends`, `/league/environment`, `/league/shooting` | League averages by season |
| `/meta`, `/api/health` | Season range and load time; liveness check |
| `/models/mvp`, `/models/mvp/{season}` | MVP model accuracy and feature importance; one season's predicted race next to the real vote |
| `/models/champion`, `/models/champion/{season}` | Champion model accuracy, weights and misses; every team's title chances one season (backtest, current or preseason) next to what happened |
| `/models/archetypes`, `/models/archetypes/{role}?decade=`, `/players/{id}/archetypes` | The roles, their share of minutes by season and example players; one role's player-seasons; a player's role each season |
| `/players/{id}/projection`, `/models/projections` | A current player's next three seasons with ranges and comparables; backtest accuracy plus projected risers, decliners and top scorers |
| `/search?q=` | Natural-language search: the filters it understood, any words it ignored, and the ranked player-seasons or careers (`drop=` removes a filter, `scope=` switches seasons/careers); "average" / "per game" questions answer with per-game numbers (`stat_is_avg`), and a titles question about a team ("how many rings do the Lakers have") returns `team_results` instead of a player ranking; a question it cannot answer as asked (team win-loss records or payroll, opponent or playoff-round filters, two teams, data it does not have, an unrecognized stat) returns `unsupported` entries with an explanation and, where one exists, a link to the page that has the answer, instead of an unrelated ranking, and a filter it had to drop is listed there too (`blocking` false) with no direct answer stated. `fallback_query` in `routers/search.py` is the hook where a smarter parser can be plugged in later |
| `/players/{id}/gamelog?season=&type=`, `/players/{id}/highs?type=` | A player's games in a season (regular or playoffs); career highs, milestone counts and best scoring games |
| `/head-to-head/teams?a=&b=`, `/head-to-head/players?a=&b=` | Two franchises' records, playoff series and recent games; two players' records and averages when they faced each other |
| `/players/{id}/salaries`, `/teams/{franchise}/salaries` | A player's salary by season with league rank, and his current contract; a franchise's payroll by season (paid, then committed), its salary sheet, and the cap and tax lines |
| `/games/coverage` | Which seasons have game-by-game data, and which playoffs are missing |
| `/players/{id}/playoffs`, `/teams/{franchise}/playoffs` | Playoff seasons, career line and titles; a franchise's titles, Finals trips and every season's result |
| `/playoffs/champions`, `/leaders/playoffs` | Every champion and runner-up; career playoff leaderboard |
| `POST /lineups/score` | Score up to five player-seasons (no account needed) |
| `/lineups/player-seasons/{id}`, `/lineups/public`, `/lineups/{id}` | A player's seasons with lineup ratings; recently shared lineups; one lineup with its live score |
| `POST/PUT/DELETE /lineups…`, `/me/lineups` | Save, edit and delete your lineups (signed in) |
| `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me` | Accounts: sign up, sign in/out, who's signed in, profile edits, `POST /auth/password`, `DELETE /auth/me` |
| `/me/favorites`, `/me/comparisons` | Your favorites and saved comparisons (signed in) |
| `/users/{username}` | A public profile: shared lineups and comparisons |

Example: `curl "localhost:8000/api/v1/compare/players?a=chambwi01&b=onealsh01&basis=index&position=3"` puts Wilt's 1962 season and Shaq's third season side by side, each relative to its own league.

### Accounts and security

Accounts are built into the API, so there's no outside auth service. Passwords are hashed with Argon2id. Sessions use a random token in an HttpOnly, SameSite=Lax cookie (Secure over HTTPS), and only its SHA-256 is stored, so sign-out and password changes revoke sessions on the server. State-changing requests must be JSON from this site, which blocks cross-site form posts. Failed sign-ins and new sign-ups are rate limited per IP and per email. Accounts and how users sign in are separate tables (`users` and `auth_identities`), so "Sign in with GitHub/Google" can be added as another identity type without changing existing accounts. Account tables are never touched by the stats reload, which is tested.

| Environment variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string. Without it, a local SQLite file is used. |
| `CORS_ORIGINS` | Sites allowed to *read* the API from the browser (default `*`). Writes are same-site only. |
| `TRUSTED_ORIGINS` | Extra origins allowed to send signed-in writes, if the frontend is hosted on another domain. |
| `COOKIE_SECURE` | Force the session cookie's Secure flag on (`1`) or off (`0`); by default it follows HTTPS. |
| `FORWARDED_ALLOW_IPS` | Proxies whose `X-Forwarded-*` headers are trusted (Docker image default `*`, right for Render). |

**Accounts need a persistent database in production.** The Docker image's SQLite file lives inside the container, and Render's free plan resets the container on every deploy and whenever it sleeps, which is fine for the stats (rebuilt from `data/`) but erases accounts. Set `DATABASE_URL` to a PostgreSQL database before letting people sign up (see below).

### Deploying

**Render (free, one click):** the repo includes a `render.yaml` Blueprint. In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint**, pick this repo, and click **Apply**. Render builds the `Dockerfile` (React build, then the API with a built-in SQLite database) and serves everything at `https://<service-name>.onrender.com`. Every push to `main` redeploys, so the weekly data-update workflow keeps the live site current with no database to manage. Free instances sleep after 15 idle minutes and take about a minute to wake on the next visit.

**Size and startup time:** with game-by-game data the database is about 260 MB on PostgreSQL (fits a 0.5 GB free tier; player-games are stored compactly for this) and about 240 MB as SQLite. A full load takes about 40 seconds on PostgreSQL (bulk `COPY`) and about 75 seconds on SQLite. The Docker image builds its SQLite database at build time, so it starts immediately; a PostgreSQL deployment loads once on first start and after each deploy with new data, so allow the host's startup or health-check timeout at least two minutes.

**With PostgreSQL (needed for accounts):** create a database (for example on Neon or Supabase; Render's own free PostgreSQL is deleted after 30 days), and add `DATABASE_URL` to the Render service's environment variables. On its first start the server loads the stats and creates the account tables; after that, every deploy with new data (including the weekly update) reloads the stats tables automatically and leaves accounts alone.

The same `Dockerfile` runs on any Docker host (Railway, Fly.io, a VPS); the container listens on `$PORT` (default 8000).

To host the React app separately (for example on GitHub Pages) against a deployed API, build it with `VITE_BASE=/nba-site-remade/ VITE_API_BASE=https://your-api.example.com npm run build`, then copy `dist/index.html` to `dist/404.html` so deep links work, and publish `dist/`. Set `CORS_ORIGINS` on the API to your site's URL (defaults to `*`).

## Project structure

```
frontend/                  React + TypeScript app (Vite)
  src/App.tsx              Layout, navigation and routes (each page lazy-loaded)
  src/api/                 Typed API client with caching, response types, useApi hook
  src/lib/                 Formatting, chart theme, URL-state hooks (useQueryParam)
  src/components/          Shared UI: charts, pills, sliders, player search
  src/auth.tsx             Signed-in user state (AuthProvider / useAuth)
  src/pages/               Overview, Evolution, Leaderboards, player/, teams/, compare/, lineups/, account/, models/
  src/**/*.test.ts         Unit tests (Vitest)
backend/
  app/main.py              FastAPI app: routers, gzip, CORS, serves frontend/dist with deep-link fallback
  app/schema.py            Database tables (SQLAlchemy Core; PostgreSQL or SQLite)
  app/db.py                Connection from DATABASE_URL (defaults to backend/nba.db)
  app/era.py               Era adjustment, mirroring src/js/era-stats.js
  app/search.py            Natural-language query parser (question -> filters)
  app/lineup.py            Lineup scoring model (percentiles vs. each season's league; graded vs. real starting fives)
  app/accounts_schema.py   Account tables, kept separate from the stats tables
  app/security.py          Password hashing, sessions, cross-site and rate-limit protections
  app/routers/             players, teams, league, compare, search, awards (models), auth, me (favorites/comparisons/profiles), lineups
  etl/load_db.py           data/*.json -> database (full refresh in one transaction)
  tests/                   API tests (pytest), run on SQLite and PostgreSQL in CI
Dockerfile, docker-compose.yml, render.yaml   Container build, local full stack, Render deploy
index.html                 Static, no-server build (generated by build.py; GitHub Pages)
build.py                   Bundles src/ + data/ into index.html
src/                       Source of the static build
  template.html            Page markup
  styles.css               All styling
  js/                      Application modules, concatenated in the order listed in build.py
    core.js                  shared helpers, core data indexes, chart theme
    data-source.js           on-demand loading hooks (no-ops in the static build)
    extended-data.js         advanced stats, per-100, All-Star, draft, league environment
    era-stats.js             raw / per-100 / era-adjusted stat definitions
    overview.js, evolution.js, leaderboards.js
    player-*.js              Player Explorer panels (explorer, awards, advanced, role, data)
    shot-court.js, shot-profile.js
    team-map.js, team-roster.js, team-explorer.js
    compare-players.js       player comparison + career overlay chart
    compare-teams.js, compare-nav.js
    similar-players.js       Similar Players panel
    main.js                  bootstrap (runs last)
  vendor/                  Chart.js, D3, topojson-client (bundled, so it works offline)
data/                      Compact JSON the dashboard embeds (generated, committed)
scripts/
  update_season.py         One-command data refresh (download, check, rebuild, test)
  prep_data.py             Raw CSVs -> data/*.json
  prep_playoffs.py         Game data + Deo Cheng series -> playoff series, titles, playoff stats (data/playoff_*.json, player_titles.json)
  prep_recent_honors.py    Award voting and All-NBA teams for seasons the main dataset lacks (from Deo Cheng, cross-checked)
  prep_salaries.py         Salaries (1996-97 on, matched to players by name) and current contracts -> data/player_salaries.json, contracts.json
  build_finals_mvp.py      Finals MVP by season, verified against official counts -> data/finals_mvp.json
  prep_games.py            Game-by-game data from three sources, checked game by game -> data/games/*.csv.gz
  extract_deocheng_pbp_slice.py  Cuts play-by-play and ESPN box scores (2024 on) out of Deo_Cheng_NBA.zip
  extract_deocheng_slice.py  Cuts a small slice out of the huge Deo_Cheng_NBA.zip (2024 onward + honors, awards, EPM, salaries)
  train_mvp.py             Trains and backtests the MVP model -> data/mvp_model.json
  train_champion.py        Trains and backtests the champion model -> data/champion_model.json
  train_archetypes.py      Clusters player-seasons into playing styles and style mixes -> data/archetypes.json
  train_similarity.py      Similar players from fingerprints + style mixes -> data/similar_players.json
  train_projections.py     Backtests and builds career projections -> data/projections.json
  franchise_map.py         Team-name -> franchise lineage, cities and coordinates
  team_colors.py           Franchise colors and badge codes
  build_map_data.js        US/Canada topology -> data/states-10m.json, canada_topo.json
tests/e2e_test.py          Browser test of the React app: every page, deep links, URL state
tests/smoke_test.py        Browser test of the static build
.github/workflows/         Weekly data update; API, frontend and browser tests on every push
```

## Updating to the latest season

```bash
pip install -r requirements.txt kaggle
kaggle auth login                      # or: export KAGGLE_API_TOKEN=... (kaggle.com/settings/api)
python3 scripts/update_season.py
```

This downloads the latest [NBA Stats (1947-present)](https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats) dataset, checks that every file and column the pipeline needs is still there, regenerates `data/*.json`, rebuilds `index.html`, runs the smoke test (if Playwright is installed) and prints what changed. If any step fails, `data/` and `index.html` are restored. New seasons need no code changes; the season range in the UI comes from the data.

It then refreshes playoffs, rings, Finals MVP and game-by-game data from the [Deo Cheng NBA database](https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026): it downloads that zip (large: it includes an 18.6M-row play-by-play table), cuts two small slices from it, rebuilds 2024-25 onward, checks rings and Finals MVPs against official counts and each season's game coverage, then deletes the download. The same Kaggle token covers both datasets. Set `DEOCHENG_DATASET` (or `GONZALO_DATASET`) if a dataset's address changes, for example when it's renamed for a new season; on GitHub, add it under Settings > Secrets and variables > Actions > Variables. The box-score dataset ends with 2023-24 and isn't downloaded each week; `--rebuild-base` (a checkbox on the Actions tab) downloads it and rebuilds those seasons, with identical results unless the dataset itself changed.

- No Kaggle account? Download the zip from the dataset page and run `python3 scripts/update_season.py --zip path/to/archive.zip`. For the Deo Cheng data use `--deocheng-zip path/to/Deo_Cheng_NBA.zip`, or `--deocheng-slices SLICE PBP_SLICE` with folders cut by the two `scripts/extract_deocheng_*.py` scripts. `--no-games` skips that part.
- **New or renamed team** (e.g. an expansion team): the script stops and names it. Add it to `TEAM_META` (and `CITY_COORDS` for a new city) in `scripts/franchise_map.py`, and to `TEAM_COLORS` in `scripts/team_colors.py` if it's a new franchise, then rerun.
- **Automatic updates:** `.github/workflows/update-data.yml` runs the same script every Monday and commits any new data, including `data/games/`. Add a repository secret named `KAGGLE_API_TOKEN` to turn it on; you can also run it from the Actions tab, where a checkbox lets you skip the large game-data download.

## Rebuilding

Editing the UI only needs Python 3:

```bash
python3 build.py        # regenerates index.html from src/ and data/
```

To regenerate the data from CSVs you already have: `python3 scripts/prep_data.py path/to/csv/folder && python3 scripts/train_mvp.py && python3 scripts/train_champion.py && python3 scripts/train_archetypes.py && python3 scripts/train_similarity.py && python3 scripts/train_projections.py && python3 build.py`.

To regenerate the map outlines (optional): `npm install && npm run build:map-data`.

## Tests

```bash
python3 -m pytest backend/tests                                     # API tests (SQLite)
TEST_DATABASE_URL=postgresql://... python3 -m pytest backend/tests    # same tests on PostgreSQL
(cd frontend && npm run typecheck && npm test)                      # TypeScript + unit tests
pip install playwright && playwright install chromium
python3 tests/e2e_test.py http://localhost:8000                     # React app in a browser (server running)
python3 tests/smoke_test.py                                         # static build in a browser
```

## Data notes

**Game-by-game data** (`data/games/`, one games file and one player-games file per season, ~26 MB) is built by `scripts/prep_games.py` from three sources, chosen game by game. The rule throughout: a game shows player stats only if its players' points add up to both teams' final scores.

- Through 2023-24: Basketball-Reference box scores (the "NBA All Time Stats" dataset). Points add up in 99.8% of games. These files are frozen; they're rebuilt only with `--base data/raw_games`.
- 2024-25 on: the Deo Cheng player game log when a game's points add up; otherwise the game is rebuilt from Deo Cheng's play-by-play (two event formats), keeping a game-log row for each player whose points and rebounds agree with the rebuild and leaving assists, minutes, fouls, the offensive/defensive rebound split and +/- empty for the rest (they can't be rebuilt reliably). Player ids are resolved through spelling-proof name matching ("A. Sengun" = "Alperen Şengün"), and deocheng's PHL/PHX-style ids are normalized.
- Validation: the same assembly run on 2023-24, where the box scores are the truth, completed 1,228 of 1,230 games, matched every stat in 99.9-100% of player-games (minutes 98.7%), and got every visitor and score right. For the newest seasons: 2024-25 regular season 1,227 of 1,230 games complete, 2025-26 regular season 1,164 of 1,230, 2025-26 playoffs 85 of 85. The 2024-25 playoffs have no box scores or play-by-play in either dataset.
- Player ids: the source's own Basketball-Reference ids are sometimes a namesake ('D. Mitchell' credited to a Mitchell from decades ago, 'AJ Green' to A.C. Green), and the points still add up, so the score check can't catch it. Every row is checked against the team's roster that season (from this project's Basketball-Reference season data): the NBA's own player id from the game log decides first, then the name on that team's roster; a row that still can't be placed is dropped, and its game shows no player stats rather than wrong ones.
- Gap filler, `scripts/prep_games_eoin.py`: the [eoinamoore dataset](https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores) (updated daily) adds games the files above lack: the 2024-25 playoffs and play-in, the last 2025-26 games, and the 2026-27 season so far. It never changes an existing row and skips preseason and All-Star games. Added rows are marked `src = eoin`. Every game from 2019-20 on also carries a `kind` (regular, playoffs, play_in or cup_final): like the NBA, the site counts play-in games and the NBA Cup championship game in no regular-season log, high, milestone, record or head-to-head. A game's player rows are saved only if the points add up; a game with a player missing from our player table (a rookie) is saved as incomplete and redone on the next run. Check the dataset's license before publishing anything built on it.
- The weekly update stops (and restores the previous files) if a season falls below 90% complete games, so a worse source can't silently replace better data.

Playoffs, rings and game-level data come from two further sources, used for what each can be trusted with (checked on the 2023-24 season they share):

- **Basketball-Reference game data** ([NBA All Time Stats](https://www.kaggle.com/datasets/gonzalogigena/nba-all-time-stats), `gonzalogigena/nba-all-time-stats`: `schedule.csv`, `boxscores_by_year/`; put it in `data/raw_games/`). Player points add up to the final score in 99.8% of games (100% of playoff games), so it is the source for player playoff stats and rosters. This copy ends with the 2023-24 playoffs and lacks one Game 7.
- **Deo Cheng NBA database** ([NBA data 1946-2026](https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026), `deocheng/nba-data-1946-2026`; `scripts/extract_deocheng_slice.py` cuts a small slice out of the huge zip into `data/raw_deocheng/`). Its playoff **series** table matched the first source's 2024 series 15 of 15 (and includes the Game 7), so series, champions and team results come from it for 2024 onward; its honors table audits rings and Finals MVPs. Not used: its game log (missing about 8% of games and nearly all playoff box scores), its per-player playoff totals (they omit many rotation players, e.g. Towns and Mobley in 2024), and the team names in its games table (wrong for many playoff games).

`python3 scripts/prep_playoffs.py data/raw_games --deocheng data/raw_deocheng/slice/slice` builds the playoff files (without `data/raw_games` it keeps the committed box-score results and rebuilds only the Deo Cheng part; the outputs are identical), then `python3 scripts/build_finals_mvp.py data/raw_deocheng` checks and writes Finals MVPs (a short hand-entered public record, verified against the official counts). Rings count every season a player was on the champion's roster, including players who never appear in a box score; those are credited up to the official "Nx NBA Champ" count using regular-season team membership.

Archetypes are learned from 1979-80 on, when every style stat exists; older seasons are placed in the nearest role using the stats they have (no three-point line before 1979-80; no blocks, steals or usage before the mid-1970s), so early-era roles are rougher. Stretch bigs are too rare (<1% of minutes) for clustering to separate and are defined by a rule instead.

Award voting and All-NBA/All-Defense/All-Rookie teams come from the Basketball-Reference dataset, which stops at 2024-25 for awards; later seasons are added from the Deo Cheng copy of the same tables by `scripts/prep_recent_honors.py`, which first checks that both sources agree row for row on the seasons they share (they match exactly for 2023-2025).

The models are trained offline (`scripts/train_*.py`, scikit-learn) and only their results ship to the server, so the API needs no ML libraries. `update_season.py` retrains them with each data update. From 2023-24 the NBA requires 65 games for MVP, with exceptions this data can't see, so the model leaves out players under 62 games and flags 62-64.


If you publish the API openly, check the license terms on the [Kaggle dataset page](https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats) and credit Basketball-Reference.


Stats come from Basketball-Reference (regular season, 1947–2026). ABA seasons are excluded from league averages. Coverage varies by stat: minutes from 1951-52, steals/blocks, BPM, VORP and per-100 stats from 1973-74, usage from 1977-78, shot-zone and play-by-play tracking from 1996-97. Era-adjusted indexes estimate league minutes as 240 per team-game. Similarity scores use players with 3,000+ tracked career minutes. Head-to-head results come from the game-by-game data described above. Team colors are used instead of logos (logos are trademarked).

## Tech

Backend: Python, [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), PostgreSQL/SQLite, pandas for the data pipeline. Frontend: [React](https://react.dev/) 18 + TypeScript, [Vite](https://vitejs.dev/), [React Router](https://reactrouter.com/), [Chart.js](https://www.chartjs.org/), [D3](https://d3js.org/) (map projection) and [TopoJSON](https://github.com/topojson/topojson); Vitest and Playwright for tests. The static build is vanilla HTML/CSS/JS. Map boundaries from [us-atlas](https://github.com/topojson/us-atlas) and [world-atlas](https://github.com/topojson/world-atlas).

## License

MIT — see [LICENSE](./LICENSE).
