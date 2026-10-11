#!/usr/bin/env python3
"""Headless smoke test for index.html. Exercises every tab and fails on any
JavaScript error or missing content.

Usage:  pip install playwright && playwright install chromium
        python3 tests/smoke_test.py
(The React app has its own test: tests/e2e_test.py.)
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else (ROOT / 'index.html').as_uri()
LATEST = str(max(e['season'] for e in json.loads((ROOT / 'data' / 'era_trends.json').read_text())))
failures, errors = [], []

def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)

def tab(page, view):
    page.click(f'#main-tabs > .tab-btn[data-view="{view}"]')
    page.wait_for_timeout(500)

def pick_player(page, input_sel, results_sel, query):
    page.fill(input_sel, query)
    page.wait_for_timeout(300)
    page.locator(f'{results_sel} .psr-item').first.click()
    page.wait_for_timeout(900)   # allows an API round trip

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1400, 'height': 1200})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector('.ticker-cell', timeout=15000)   # API mode loads data first
    page.wait_for_timeout(500)

    print('Overview')
    check(page.locator('.ticker-cell').count() == 5, 'hero ticker has 5 cells')
    check(page.locator('#sb-season').inner_text() == LATEST, f'scoreboard shows latest season ({LATEST})')

    print('Era Evolution')
    tab(page, 'evolution')
    check(page.locator('#view-evolution canvas').count() >= 3, 'evolution charts render')

    print('Leaderboards')
    tab(page, 'leaders')
    check('LeBron James' in page.locator('#lb-tbody tr').first.inner_text(), 'LeBron leads career points')

    print('Player Explorer')
    tab(page, 'players')
    pick_player(page, '#player-search', '#player-search-results', 'jokic')
    check('Jokić' in page.locator('#pc-name').inner_text(), 'accent-insensitive search finds Jokić')
    for panel in ['#pc-awards-panel', '#pc-shooting-panel', '#pc-pbp-panel']:
        check(page.locator(panel).is_visible(), f'{panel} visible')
    check(page.locator('.court-zone').count() >= 5, 'shot court zones render')
    check('Drafted 2014' in page.locator('#pc-meta').inner_text(), 'draft info shown')
    check(page.locator('#pc-advanced-panel').is_visible(), 'advanced metrics panel visible')
    check(page.locator('.similar-row').count() >= 5, 'similar players listed')
    check(page.locator('#pc-awards-timeline .allstar-pill').count() >= 5, 'All-Star selections on awards timeline')

    print('Team Explorer')
    tab(page, 'teams')
    page.wait_for_timeout(600)
    check(page.locator('g.team-marker').count() >= 30, 'map shows every current team')
    markers = page.locator('g.team-marker')
    for i in range(markers.count()):
        if markers.nth(i).locator('.marker-badge-text').text_content() == 'BOS':
            markers.nth(i).click()
            break
    page.wait_for_timeout(600)
    check(page.locator('#roster-tbody tr').count() > 10, 'Celtics roster loads')

    print('Compare: players')
    tab(page, 'compare')
    page.locator('#cmp-player-suggestions .pill-btn').first.click()
    page.wait_for_timeout(600)
    page.locator('#cmp-align-slider').fill('5')
    page.wait_for_timeout(300)
    check('Year 5' in page.locator('#cmp-align-note').inner_text(), 'experience alignment works')
    page.click('#cmp-basis-toggle button[data-basis="index"]')
    page.wait_for_timeout(300)
    check('scoring rate' in page.locator('#cmp-stat-table').inner_text().lower(), 'era-adjusted basis renders')
    page.click('#cmp-view-toggle button[data-cmpview="overlay"]')
    page.wait_for_timeout(500)
    check(page.locator('#cmp-overlay-view').is_visible(), 'career overlay chart opens')
    page.click('#cmp-view-toggle button[data-cmpview="snapshot"]')

    print('Compare: teams')
    page.click('button[data-compare-mode="teams"]')
    page.wait_for_timeout(300)
    opts = page.eval_on_selector_all('#cmp-team-select-a option', 'els => els.map(e => e.textContent)')
    page.select_option('#cmp-team-select-a', label=[o for o in opts if 'Boston Celtics' in o][0])
    page.select_option('#cmp-team-select-b', label=[o for o in opts if 'Los Angeles Lakers' in o][0])
    page.wait_for_timeout(500)
    check(page.locator('.award-summary-badge').count() > 5, 'team accomplishments summarized')

    browser.close()

print()
if errors:
    print('JavaScript errors:'); [print('  ', e) for e in errors]
if failures or errors:
    print(f'{len(failures)} check(s) failed, {len(errors)} JS error(s)')
    sys.exit(1)
print('All checks passed')
