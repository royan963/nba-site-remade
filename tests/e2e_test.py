#!/usr/bin/env python3
"""Browser test for the React app (frontend/), served by the API.

Usage:  uvicorn backend.app.main:app --port 8000   (with frontend/dist built)
        python3 tests/e2e_test.py [http://localhost:8000]
Requires: pip install playwright && playwright install chromium
"""
import re
import sys
import time
from urllib.parse import unquote
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000').rstrip('/')
failures, errors = [], []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)


def open_page(page, path):
    page.goto(BASE + path)
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(300)


def path_of(page):
    return page.url[len(BASE):]


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1300, 'height': 1000})
    page.on('pageerror', lambda e: errors.append(str(e)))

    print('Overview')
    open_page(page, '/')
    check(page.locator('.ticker-cell').count() == 5, 'hero ticker has 5 cells')
    check('LeBron James' in page.locator('#hero-ticker').inner_text(), 'all-time scorer comes from the API')
    start = page.locator('#sb-season').inner_text()
    page.locator('#season-slider').fill('1962')
    check(page.locator('#sb-season').inner_text() == '1962' and start != '1962', 'season slider moves the scoreboard')

    print('Navigation and URL state')
    page.click('#main-tabs >> text=Leaderboards')
    page.wait_for_load_state('networkidle')
    check(path_of(page) == '/leaders', 'tab click changes the URL')
    page.select_option('#lb-stat-select', 'ws')
    page.wait_for_timeout(600)
    check('stat=ws' in page.url, 'leaderboard stat is saved in the URL')
    check('LeBron James' in page.locator('#lb-tbody tr').first.inner_text(), 'Win Shares leader loads')
    page.reload(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(400)
    check(page.locator('#lb-stat-select').input_value() == 'ws', 'reload keeps the leaderboard state')
    page.fill('#lb-search', 'krejci'); page.wait_for_timeout(900)
    rows = page.locator('#lb-tbody tr')
    check(rows.count() == 1 and 'Krej' in rows.first.inner_text(), 'name filter is accent-insensitive (server-side)')

    print('Player page')
    open_page(page, '/players')
    page.fill('#player-search', 'jokic'); page.wait_for_timeout(600)
    page.locator('.psr-item').first.click(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(600)
    check(path_of(page) == '/players/jokicni01', 'search navigates to /players/<id>')
    check('Jokić' in page.locator('#pc-name').inner_text(), 'player header renders')
    page.wait_for_selector('#pc-advanced-panel', timeout=15000)
    for sel in ['#pc-advanced-panel', '#pc-similar-panel', '#pc-awards-panel', '#pc-shooting-panel', '#pc-pbp-panel']:
        check(page.locator(sel).is_visible(), f'{sel} visible')
    check(page.locator('.similar-row').count() >= 5, 'similar players listed')
    check(page.locator('.court-zone').count() == 7, 'shot court has 7 zones')
    page.locator('.similar-compare').first.click(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(500)
    check(re.match(r'^/compare/players/jokicni01/\w+', path_of(page)) is not None, 'Compare button opens a comparison link')
    page.go_back(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(400)
    check(path_of(page).startswith('/players/jokicni01'), 'browser Back returns to the player')

    open_page(page, '/players/curryst01?stat=ts_pct&shotView=bars&shot=2016')
    check(page.locator('#pc-stat-pills .pill-btn.active').inner_text() == 'TS%', 'deep link selects the chart stat')
    check(page.locator('[data-testid="shot-bars"]').count() == 1, 'deep link opens the shot bar chart')
    check(page.locator('#pc-shooting-season').input_value() == '2016', 'deep link selects the shot season')
    open_page(page, '/players/nobody00')
    check('No player' in page.locator('#view-players').inner_text(), 'unknown player shows an error, not a crash')

    print('Teams')
    open_page(page, '/teams?season=1950')
    n1950 = page.locator('g.team-marker').count()
    check(15 <= n1950 <= 25, f'1950 map shows the small early league ({n1950} markers)')
    open_page(page, '/teams')
    check(page.locator('g.team-marker').count() >= 30, 'current map shows every team')
    page.locator('g.team-marker').last.click(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(500)
    check(path_of(page).startswith('/teams/'), 'clicking a marker opens /teams/<franchise>')
    open_page(page, '/teams/boston-celtics?roster=1986')
    check(page.locator('#tc-name').inner_text() == 'Boston Celtics', 'franchise detail renders')
    page.wait_for_timeout(500)
    check('Larry Bird' in page.locator('#roster-tbody tr').first.inner_text(), 'roster deep link loads 1986 Celtics')
    open_page(page, '/teams?view=list')
    check(page.locator('.team-chip').count() == 44, 'list view shows all 44 franchises')

    print('Compare')
    open_page(page, '/compare/players/jamesle01/jordami01?pos=5')
    check('Year 5' in page.locator('#cmp-align-note').inner_text(), 'comparison deep link opens at Year 5')
    page.click('#cmp-basis-toggle >> text=Era-adjusted (vs. league)'); page.wait_for_timeout(600)
    check('basis=index' in page.url and 'scoring rate' in page.locator('#cmp-stat-table').inner_text().lower(), 'era-adjusted basis (URL + table)')
    page.click('#cmp-view-toggle >> text=Career overlay chart'); page.wait_for_timeout(500)
    check(page.locator('[data-testid="cmp-overlay-chart"]').count() == 1 and 'view=overlay' in page.url, 'career overlay chart')
    open_page(page, '/compare/players/curryst01/thompkl01?align=calendar&pos=2017')
    check('teammates' in page.locator('#cmp-h2h-panel').inner_text(), 'teammates detected in a shared season')
    open_page(page, '/compare/teams/boston-celtics/los-angeles-lakers')
    page.wait_for_timeout(500)
    check(page.locator('.award-summary-badge').count() > 5, 'team accomplishments summarized')
    open_page(page, '/compare/teams/boston-celtics/los-angeles-lakers?scope=season&sa=2008&sb=2008')
    check('66-16' in page.locator('#cmp-team-card-a').inner_text(), 'season scope: 2008 Celtics went 66-16')

    print('Models')
    open_page(page, '/models')
    check(path_of(page) == '/models/mvp', '/models opens the MVP predictor')
    check(page.locator('#mvp-tbody tr').count() >= 10, 'MVP race table lists candidates')
    check('%' in page.locator('#mvp-accuracy').inner_text(), 'model accuracy card')
    page.wait_for_selector('#mvp-preseason-note', timeout=15000)
    check('(preseason)' in page.locator('#mvp-race .section-title').inner_text().lower() and page.locator('#mvp-preseason-note').count() == 1,
          'opens on the upcoming preseason race')
    open_page(page, '/models/champion')
    page.wait_for_selector('#champion-preseason-note', timeout=15000)
    check('(preseason)' in page.locator('#champion-race .section-title').inner_text().lower()
          and page.locator('#champion-tbody tr').count() >= 28, 'champion predictor opens on the preseason odds, every team listed')
    page.select_option('#champion-season', '1996'); page.wait_for_timeout(700)
    check('season=1996' in page.url and 'Chicago Bulls' in page.locator('#champion-verdict').inner_text(), 'champion backtest season via picker + URL')
    page.locator('.champion-miss').first.click(); page.wait_for_timeout(700)
    check(page.locator('#champion-verdict').inner_text().startswith('The model favored'), 'clicking a miss opens that season')
    open_page(page, '/models/mvp')
    page.select_option('#mvp-season', '1962'); page.wait_for_timeout(700)
    check('season=1962' in page.url and 'Bill Russell' in page.locator('#mvp-verdict').inner_text(), 'backtest season via picker + URL')
    page.locator('.mvp-miss').first.click(); page.wait_for_timeout(700)
    check(page.locator('#mvp-verdict').inner_text().startswith('The model picked') , 'clicking a miss opens that season')

    open_page(page, '/models/archetypes')
    check(page.locator('.archetype-card').count() == 10, 'ten archetype cards')
    check(page.locator('[data-testid="archetype-chart"]').count() == 1, 'role trend chart')
    page.locator('.archetype-card[data-role="rim-protector"] .archetype-more').click(); page.wait_for_timeout(800)
    check('role=rim-protector' in page.url and page.locator('#role-players tbody tr').count() > 10, 'open a role (URL + player list)')
    open_page(page, '/players/lopezbr01')
    check('Stretch big' in page.locator('#pc-style-strip').inner_text(), 'player page shows playing style by season')
    mix = page.locator('#pc-style-mix').inner_text()
    check('Stretch big' in mix and 'Scoring big' in mix, 'player page shows a mix of playing styles')
    check(page.locator('.similar-styles').count() >= 5, 'similar players show each match\u2019s styles')

    open_page(page, '/models/projections')
    check(page.locator('#projection-accuracy tbody tr').count() == 3, 'projection accuracy table (3 horizons)')
    check(page.locator('#proj-risers tbody tr').count() >= 5, 'projected risers list')
    open_page(page, '/players/wembavi01')
    check(page.locator('#pc-projection-table tbody tr').count() == 3, 'player page shows a 3-season projection')
    labels = page.evaluate("document.querySelector('[data-testid=player-chart]').chart.data.labels")
    check(labels[-1] == labels[-4] + 3, 'career chart extends three seasons into the projection')
    open_page(page, '/players/jordami01')
    check(page.locator('#pc-projection-panel').count() == 0, 'retired players have no projection')

    print('Search')
    open_page(page, '/')
    page.fill('#header-search', 'best rebounding guards of the 90s'); page.press('#header-search', 'Enter')
    page.wait_for_load_state('networkidle'); page.wait_for_timeout(700)
    check(path_of(page).startswith('/search?q=best'), 'header search opens the search page')
    check('guards' in page.locator('#search-chips').inner_text(), 'search shows how the question was read')
    check(page.locator('#search-tbody tr').count() >= 10, 'search returns ranked results')
    page.click('#search-chips button[aria-label="Remove guards"]'); page.wait_for_load_state('networkidle'); page.wait_for_timeout(600)
    check('drop=' in page.url and 'Rodman' in page.locator('#search-tbody tr').first.inner_text(), 'removing a filter reruns the search')
    open_page(page, '/search?q=michael%20jordan')
    check('Michael Jordan' in page.locator('#search-names').inner_text(), 'a name finds the player')

    print('Playoffs')
    open_page(page, '/players/jordami01')
    check('6\u00d7 NBA champion' in page.locator('#pc-titles').inner_text() and '1998' in page.locator('#pc-titles').inner_text(), 'player header shows championships')
    check(page.locator('#pc-playoffs-table tbody tr').count() >= 14 and 'Champion' in page.locator('#pc-playoffs-table').inner_text(), 'playoff stats table with results')
    open_page(page, '/players/gilgesh01')
    page.wait_for_selector('#pc-playoffs-table', timeout=15000)
    seasons = [r.split('\t')[0].strip('* ') for r in page.locator('#pc-playoffs-table tbody tr').all_inner_texts()]
    check('2025' in seasons and '2026' in seasons and page.locator('#pc-playoffs-sources').count() == 1,
          'newest playoff seasons listed, with where their stats come from')
    page.click('#pc-season-type >> text=Playoffs'); page.wait_for_timeout(600)
    check('type=playoffs' in page.url and page.evaluate("document.querySelector('[data-testid=player-chart]').chart.data.datasets[0].label").endswith('(playoffs)'), 'career chart switches to playoffs')
    open_page(page, '/teams/boston-celtics')
    check('18' in page.locator('#team-playoff-summary').inner_text() and '1957' in page.locator('#team-title-years').inner_text(), 'team page shows 18 championships')
    open_page(page, '/teams?view=champions&season=1998')
    check(page.locator('#champions-table tbody tr').count() == 80, 'champions list covers every season')
    check('Chicago Bulls' in page.locator('#champions-table tr[data-season="1998"]').inner_text() and 'Michael Jordan' in page.locator('#champions-table tr[data-season="1998"]').inner_text(), 'champions list shows the 1998 champion and Finals MVP')
    open_page(page, '/leaders?type=playoffs')
    check('LeBron James' in page.locator('#lb-tbody tr').first.inner_text(), 'playoff leaderboard: LeBron leads career playoff points')
    open_page(page, '/leaders?type=playoffs&stat=titles')
    check('Bill Russell' in page.locator('#lb-tbody tr').first.inner_text(), 'playoff leaderboard by championships')
    open_page(page, '/compare/teams/boston-celtics/los-angeles-lakers')
    page.wait_for_timeout(600)
    check('championships' in page.locator('#cmp-team-stat-table').inner_text().lower() and '18' in page.locator('#cmp-team-card-a').inner_text(), 'team comparison shows championships')

    print('Game-by-game')
    open_page(page, '/players/jordami01?gl=1998&glt=playoffs')
    page.wait_for_selector('#pc-gamelog-table', timeout=15000)
    rows = page.locator('#pc-gamelog-table tbody tr')
    check(rows.count() == 22, 'game log: 21 playoff games plus averages for 1998')
    check('45' in page.locator('#pc-gamelog-table tbody tr', has_text='1998-06-14').inner_text(), 'game log: 45 points in Game 6, June 14 1998')
    open_page(page, '/players/chambwi01?hit=regular')
    page.wait_for_selector('#pc-highs', timeout=15000)
    check('100' in page.locator('#pc-highs').inner_text() and '1962-03-02' in page.locator('#pc-highs').inner_text(), "career highs: Wilt's 100-point game")
    check('118' in page.locator('#pc-milestones').inner_text(), 'career highs: Wilt has 118 50-point games')
    open_page(page, '/compare/teams/boston-celtics/los-angeles-lakers')
    page.wait_for_timeout(800)
    check('9\u20133' in page.locator('#cmp-team-h2h-record').inner_text(), 'team head-to-head: Celtics 9-3 in playoff series vs. the Lakers')
    open_page(page, '/compare/players/jamesle01/curryst01')
    page.wait_for_timeout(800)
    page.wait_for_selector('#cmp-h2h-panel .h2h-side', timeout=15000)
    check('playoffs: 28 games' in page.locator('#cmp-h2h-panel').inner_text().lower(), 'player head-to-head: LeBron vs. Curry, 28 playoff games')
    check('game-by-game schedule' not in page.content(), 'the old "no game-by-game data" notes are gone')
    open_page(page, '/players/jordami01')
    for _ in range(40):                       # scroll down gradually, like a reader, until the game log loads
        if page.locator('#pc-gamelog-panel').count():
            break
        page.mouse.wheel(0, 500); page.wait_for_timeout(150)
    page.wait_for_selector('#pc-gamelog-panel', timeout=15000)
    check(page.locator('#pc-gamelog-panel').count() == 1, 'game log appears when scrolled to')

    print('Salaries')
    open_page(page, '/players/gilgesh01')
    for _ in range(60):                       # the salary panel loads when scrolled to
        if page.locator('#pc-salary-stats').count():
            break
        page.mouse.wheel(0, 500); page.wait_for_timeout(150)
    page.wait_for_selector('#pc-salary-stats', timeout=15000)
    check('career earnings' in page.locator('#pc-salary-stats').inner_text().lower(), 'player salary summary')
    check('2030-31' in page.locator('#pc-contract-table').inner_text() and 'PO' in page.locator('#pc-contract-table').inner_text(),
          'contract runs through 2030-31 with a player option')
    check(page.locator('[data-testid="salary-chart"], #pc-salary-panel canvas').count() >= 1, 'salary chart')
    open_page(page, '/teams/oklahoma-city-thunder')
    page.wait_for_selector('#team-contracts-table', timeout=15000)
    check('Shai Gilgeous-Alexander' in page.locator('#team-contracts-table tbody tr').first.inner_text(), 'team salary sheet, highest paid first')
    check('luxury tax' in page.locator('#team-payroll-stats').inner_text().lower(), 'payroll vs. the cap and tax lines')

    print('Accounts')
    ctx = browser.new_context(viewport={'width': 1300, 'height': 1000})
    ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    tag = str(int(time.time()))[-7:]
    email, username, password = f'e2e{tag}@example.com', f'e2e_{tag}', 'correct horse battery staple'
    open_page(page, '/players/curryst01')
    page.click('.favorite-btn'); page.wait_for_load_state('networkidle')
    check(path_of(page).startswith('/login?next=%2Fplayers%2Fcurryst01'), 'favoriting while signed out asks you to sign in')
    page.click('text=Create an account'); page.wait_for_load_state('networkidle')
    page.fill('#signup-form input[type=email]', email)
    page.fill('#signup-form input[autocomplete=username]', username)
    page.fill('#signup-form input[type=password]', password)
    page.wait_for_timeout(900)
    check('Available' in page.locator('#signup-form').inner_text(), 'username availability check (shown in normal case)')
    page.click('#signup-form button[type=submit]'); page.wait_for_selector('#account-button', timeout=15000); page.wait_for_load_state('networkidle')
    check(path_of(page) == '/players/curryst01', 'sign-up returns you to the page you came from')
    check(page.locator('#account-button').is_visible(), 'account menu shows when signed in')
    page.click('.favorite-btn'); page.wait_for_timeout(500)
    check('Favorited' in page.locator('.favorite-btn').inner_text(), 'favorite a player')
    open_page(page, '/teams/boston-celtics')
    page.click('.favorite-btn'); page.wait_for_timeout(500)
    check('Favorited' in page.locator('.favorite-btn').inner_text(), 'favorite a team')

    open_page(page, '/compare/players/jamesle01/jordami01?basis=index&pos=5')
    page.click('#save-comparison')
    page.fill('#save-comparison-form textarea', 'Year 5, era-adjusted')
    page.check('#save-comparison-form input[type=checkbox]')
    page.click('#save-comparison-form >> text=Save'); page.wait_for_timeout(600)
    check('Saved' in page.locator('#compare-players').inner_text(), 'save a comparison')

    print('Lineups')
    open_page(page, '/lineups/new')
    page.click('text=1996 Bulls (72-10)'); page.wait_for_timeout(1500)
    check(page.locator('.lineup-slot').count() == 5, 'preset fills five slots')
    check('p=harpero01:1996,jordami01:1996' in page.url, 'unsaved lineup lives in the URL')
    overall = page.locator('.lineup-overall-value').inner_text()
    check(overall.isdigit(), f'lineup gets an overall score ({overall})')
    page.locator('.lineup-slot').nth(4).locator('button').click(); page.wait_for_timeout(300)
    page.fill('#lineup-search', 'olajuwon'); page.wait_for_timeout(700)
    page.locator('.psr-item').first.click(); page.wait_for_timeout(1500)
    check('Hakeem' in page.locator('#lineup-slots').inner_text(), 'swap in a player from search')
    page.locator('.lineup-slot').nth(4).locator('select').select_option('1994'); page.wait_for_timeout(1500)
    check('olajuha01:1994' in page.url, 'pick a specific season (readable URL)')
    page.fill('#lineup-name', 'Bulls with Dream'); page.click('#lineup-save-btn')
    page.wait_for_load_state('networkidle'); page.wait_for_timeout(800)
    m = re.match(r'^/lineups/(\d+)$', path_of(page))
    check(m is not None and page.locator('#lineup-title').inner_text() == 'Bulls with Dream', 'save a lineup and open its page')
    lineup_url = path_of(page)

    open_page(page, f'/u/{username}')
    check('Bulls with Dream' in page.locator('#view-profile').inner_text() and 'Year 5' in page.locator('#view-profile').inner_text(),
          'public profile shows the shared lineup and comparison')
    open_page(page, '/account')
    acct = page.locator('#view-account').inner_text()
    check('Stephen Curry' in acct and 'Boston Celtics' in acct, 'settings page lists favorites')

    page.click('#account-button'); page.click('text=Sign out'); page.wait_for_load_state('networkidle'); page.wait_for_timeout(400)
    check(page.locator('#sign-in-link').is_visible(), 'sign out')
    open_page(page, lineup_url)
    check(page.locator('#lineup-title').inner_text() == 'Bulls with Dream' and page.locator('#lineup-edit').count() == 0,
          'public lineup is viewable signed out, without edit controls')
    open_page(page, '/login')
    page.fill('#login-form input[type=email]', email); page.fill('#login-form input[type=password]', 'wrong password!!')
    page.click('#login-form button[type=submit]'); page.wait_for_timeout(600)
    check('Incorrect' in page.locator('#login-form').inner_text(), 'wrong password is rejected')
    page.fill('#login-form input[type=password]', password); page.click('#login-form button[type=submit]')
    page.wait_for_load_state('networkidle'); page.wait_for_timeout(500)
    check(page.locator('#account-button').is_visible(), 'sign back in')
    open_page(page, lineup_url)
    check(page.locator('#lineup-edit').count() == 1, 'owner sees edit controls')
    ctx.close()

    print('Misc')
    page = browser.new_page()
    open_page(page, '/no/such/page')
    check('Page not found' in page.locator('main').inner_text(), 'unknown route shows a not-found page')
    check('\\u20' not in page.content(), 'no literal unicode escapes in the page')
    browser.close()

print()
if errors:
    print('JavaScript errors:'); [print('  ', e) for e in errors]
if failures or errors:
    print(f'{len(failures)} check(s) failed, {len(errors)} JS error(s)')
    sys.exit(1)
print('All checks passed')
