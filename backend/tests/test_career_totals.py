"""Career totals must count each season once.

A player traded mid-season has a combined row (team 2TM, 3TM, ...) plus one row per team in player_seasons. The career
table must count that season once. Expected games are computed here from the season rows, not from prep_data.py.
"""
import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MULTI = {'2TM', '3TM', '4TM', '5TM'}


def table(name):
    d = json.loads((ROOT / 'data' / f'{name}.json').read_text(encoding='utf8'))
    return [dict(zip(d['columns'], r)) for r in d['rows']]


def test_career_games_count_a_traded_season_once():
    seasons = table('player_seasons')
    traded = {(r['player_id'], r['season']) for r in seasons if r['team'] in MULTI}
    expected = defaultdict(int)
    for r in seasons:
        if (r['player_id'], r['season']) not in traded or r['team'] in MULTI:
            expected[r['player_id']] += r['g'] or 0
    wrong = {c['player_id']: (c['g'], expected[c['player_id']]) for c in table('player_career')
             if c['player_id'] in expected and c['g'] != expected[c['player_id']]}
    assert not wrong, f'{len(wrong)} players have inflated career games, e.g. {dict(list(wrong.items())[:3])}'


def test_prep_data_dedupes_the_career_totals_by_the_combined_row():
    """prep_data.py runs on import, so read its source: the Player Totals frame must go through dedupe_multi."""
    src = (ROOT / 'scripts' / 'prep_data.py').read_text(encoding='utf8')
    assigns = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Assign)
               and any(getattr(t, 'id', None) == 'pt' for t in n.targets)]
    assert any('dedupe_multi' in ast.unparse(n.value) for n in assigns), 'career totals are not deduped by 2TM/3TM rows'
