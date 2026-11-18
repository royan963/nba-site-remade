"""Current NBA news: headlines from public RSS feeds, tagged with the players and teams they mention.

Only the headline, a one-line summary from the feed, the source, the time and the link are shown; every item links
to the publisher's own page. Feeds are fetched on demand and kept for CACHE_SECONDS, so visitors share one fetch and
the publishers see a handful of requests an hour. If a feed fails, the others still show, and the last good copy of
it is kept.
"""
from __future__ import annotations

import html
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .util import normalize_name

FEEDS = [
    ('ESPN', 'https://www.espn.com/espn/rss/nba/news'),
    ('Yahoo Sports', 'https://sports.yahoo.com/nba/rss/'),
    ('CBS Sports', 'https://www.cbssports.com/rss/headlines/nba/'),
]
CACHE_SECONDS = 15 * 60
TIMEOUT = 8.0
MAX_BYTES = 3_000_000                 # the biggest feed (Yahoo, with embedded image captions) is ~400 KB
SUMMARY_CHARS = 220
USER_AGENT = 'nba-history-explorer (news headlines; https://nba-history.onrender.com)'


# ---- fetching and parsing --------------------------------------------------------------------------------
def fetch(url: str) -> bytes:
    import httpx
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True, headers={'User-Agent': USER_AGENT}) as c:
        with c.stream('GET', url) as r:
            r.raise_for_status()
            body = b''
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise ValueError(f'{url}: feed larger than {MAX_BYTES:,} bytes')
    return body


def _text(el, tag):
    found = el.find(tag)
    return (found.text or '').strip() if found is not None and found.text else ''


def _plain(s: str) -> str:
    s = re.sub(r'<[^>]+>', ' ', html.unescape(html.unescape(s or '')))   # some feeds escape twice
    s = re.sub(r'\s+', ' ', s).strip()
    return re.sub(r'\s+([.,;:!?)])', r'\1', s)                       # a removed tag leaves no gap before punctuation


def _when(s: str) -> datetime | None:
    try:
        d = parsedate_to_datetime(s.strip())
    except (TypeError, ValueError, IndexError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def parse(source: str, body: bytes) -> list[dict]:
    """RSS 2.0 items -> [{title, link, source, published, summary}]. Feeds with a DOCTYPE are refused (no entity tricks)."""
    head = body[:2048].decode('utf-8', 'ignore')
    if '<!DOCTYPE' in head.upper() or '<!ENTITY' in body.decode('utf-8', 'ignore').upper():
        raise ValueError(f'{source}: feed declares a DOCTYPE or entities; refused')
    root = ET.fromstring(body)
    items = []
    for it in root.iter('item'):
        title, link = _plain(_text(it, 'title')), _text(it, 'link').strip()
        if not title or not re.match(r'^https?://', link):          # only real web links reach the page
            continue
        published = _when(_text(it, 'pubDate'))
        summary = _plain(_text(it, 'description'))
        if len(summary) > SUMMARY_CHARS:
            summary = summary[:SUMMARY_CHARS].rsplit(' ', 1)[0] + '…'
        items.append({'title': title, 'link': link, 'source': source,
                      'published': published.isoformat() if published else None, 'summary': summary})
    return items


def _key(title: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', normalize_name(title)).strip()


def merge(lists: list[list[dict]]) -> list[dict]:
    """All feeds' items, newest first, each story once (same link, or the same headline from two feeds)."""
    seen_links, seen_titles, out = set(), set(), []
    every = [i for lst in lists for i in lst]
    every.sort(key=lambda i: i['published'] or '', reverse=True)
    for i in every:
        k = _key(i['title'])
        if i['link'] in seen_links or k in seen_titles:
            continue
        seen_links.add(i['link'])
        seen_titles.add(k)
        out.append(i)
    return out


# ---- who and what a headline is about ----------------------------------------------------------------------
TEAM_EXTRA = {   # what headlines call teams besides their names
    'CLE': ['Cavs'], 'DAL': ['Mavs'], 'MIN': ['Wolves', 'T-Wolves', 'Timberwolves'], 'POR': ['Blazers'], 'PHI': ['Sixers'],
    'NOP': ['Pels'], 'OKC': ['OKC'], 'GSW': ['Warriors', 'Golden State', 'Dubs'], 'LAL': ['Lakers'], 'LAC': ['Clippers'],
    'SAS': ['Spurs'], 'NYK': ['Knicks'], 'BRK': ['Nets', 'Brooklyn'], 'CHO': ['Hornets', 'Charlotte'],
}
AMBIGUOUS_CITIES = {'Los Angeles', 'New York'}            # two teams each (Brooklyn has its own name)
PLAYER_NICKNAMES = {'LeBron': 'jamesle01', 'Steph': 'curryst01', 'Giannis': 'antetgi01', 'SGA': 'gilgesh01', 'Shai': 'gilgesh01',
                    'Wemby': 'wembavi01', 'Luka': 'doncilu01', 'Kawhi': 'leonaka01', 'Zion': 'williza01', 'Jokic': 'jokicni01',
                    'KAT': 'townska01', 'Ja': 'moranja01', 'Dame': 'lillada01'}
# surnames that are also everyday words or very common names: a headline using one alone is too often about something else
SURNAME_STOP = {'green', 'brown', 'white', 'black', 'love', 'holiday', 'young', 'hunter', 'rose', 'king', 'grant', 'harris',
                'johnson', 'williams', 'jones', 'smith', 'davis', 'thompson', 'jackson', 'allen', 'walker', 'mitchell', 'martin',
                'murray', 'porter', 'payne', 'wells', 'banks', 'price', 'hood', 'wood', 'house', 'hill', 'strong', 'little', 'small',
                'bell', 'cash', 'gay', 'lively', 'christie', 'collins', 'edwards', 'robinson', 'wallace', 'watson', 'reed', 'washington',
                'richards', 'clark', 'lewis', 'moore', 'taylor', 'anderson', 'thomas', 'miller', 'wilson', 'carter', 'butler', 'george',
                'james', 'paul', 'jordan', 'ball', 'hart', 'sharpe', 'dunn', 'battle', 'post', 'riley', 'sweet', 'joseph', 'nance', 'champagnie'}
SUFFIX = {'jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv'}


def strip_accents(s: str) -> str:
    """'Dončić' -> 'Doncic', keeping capitals (normalize_name also lowercases)."""
    return ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))


def _surname(name: str) -> str:
    parts = [p for p in name.split() if p.lower().strip(',') not in SUFFIX]
    return parts[-1] if parts else name


@dataclass
class Tagger:
    teams: dict                                     # abbr -> {abbr, franchise, team_name}
    players: dict                                   # player_id -> {player_id, player, team}
    patterns: list = field(default_factory=list)    # (compiled regex, kind, key)
    by_team_surname: dict = field(default_factory=dict)   # (team, surname) -> player ids, for "Grizzlies' Jackson"

    @classmethod
    def build(cls, team_rows: list[dict], player_rows: list[dict]) -> 'Tagger':
        """team_rows: this season's teams (abbr, franchise, team_name, city); player_rows: this season's players
        (player_id, player, team, g, mp), traded players once (their latest team)."""
        t = cls(teams={r['abbr']: {'abbr': r['abbr'], 'franchise': r['franchise'], 'team_name': r['team_name']} for r in team_rows},
                players={r['player_id']: {'player_id': r['player_id'], 'player': r['player'], 'team': r['team']} for r in player_rows})
        cities = {}
        for r in team_rows:
            cities.setdefault(r.get('city') or '', []).append(r['abbr'])
        for r in team_rows:
            names = {r['team_name']}
            city = r.get('city') or ''
            nickname = r['team_name'][len(city):].strip() if city and r['team_name'].startswith(city) else r['team_name'].split()[-1]
            names.add(nickname)
            if city and city not in AMBIGUOUS_CITIES and len(cities.get(city, [])) == 1:
                names.add(city)
            names.update(TEAM_EXTRA.get(r['abbr'], []))
            for n in names:
                t.patterns.append((re.compile(rf'(?<![\w-]){re.escape(n)}(?![\w-])'), 'team', r['abbr']))   # case-sensitive: proper nouns
        last_names = {}
        for r in player_rows:
            last_names.setdefault(normalize_name(_surname(r['player'])), []).append(r)
        for r in player_rows:
            t.by_team_surname.setdefault((r['team'], strip_accents(_surname(r['player']))), []).append(r['player_id'])
        for r in player_rows:
            full = normalize_name(r['player'])
            bare = ' '.join(p for p in full.split() if p.strip(',') not in SUFFIX)       # "GG Jackson" for GG Jackson II
            for name in {full, bare}:
                t.patterns.append((re.compile(rf'(?<!\w){re.escape(name)}(?!\w)', re.I), 'player_full', r['player_id']))
            sur = _surname(r['player'])
            key = normalize_name(sur)
            # a surname alone, for regulars whose surname no other current player shares and isn't an everyday word
            if (len(last_names[key]) == 1 and (r.get('mp') or 0) >= 15 and len(key) >= 4 and key not in SURNAME_STOP
                    and key not in {normalize_name(n) for n in ('Heat', 'Magic', 'Jazz', 'Thunder', 'Kings', 'Nets', 'Suns', 'Bulls')}):
                t.patterns.append((re.compile(rf'(?<!\w){re.escape(strip_accents(sur))}(?!\w)'), 'player_last', r['player_id']))
        for nick, pid in PLAYER_NICKNAMES.items():
            if pid in t.players:
                t.patterns.append((re.compile(rf'(?<!\w){re.escape(nick)}(?!\w)'), 'player_nick', pid))
        return t

    def tag(self, item: dict) -> dict:
        """Players and teams a headline (and its summary) mentions; a player's team counts as mentioned too."""
        text = f"{item['title']} • {item.get('summary') or ''}"
        plain = strip_accents(text)
        players, teams = [], []
        for rx, kind, key in self.patterns:
            hay = plain.lower() if kind == 'player_full' else plain
            if rx.search(hay):
                (teams if kind == 'team' else players).append(key)
        # a surname too common to count alone does count next to his team ("Grizzlies' Jackson"), if he's the only one there
        for (team, sur), ids in self.by_team_surname.items():
            if team in teams and len(ids) == 1 and ids[0] not in players and re.search(rf'(?<!\w){re.escape(sur)}(?!\w)', plain):
                players.append(ids[0])
        players = list(dict.fromkeys(players))
        teams = list(dict.fromkeys(teams + [self.players[p]['team'] for p in players if self.players[p]['team'] in self.teams]))
        return {**item, 'players': [{'player_id': p, 'player': self.players[p]['player'], 'team': self.players[p]['team']} for p in players],
                'teams': [self.teams[a] for a in teams]}


# ---- cache -------------------------------------------------------------------------------------------------
_lock = threading.Lock()
_cache: dict = {'at': 0.0, 'items': [], 'sources': [], 'by_feed': {}}


def latest(force: bool = False, fetcher=None) -> dict:
    """The merged feeds, refetched when older than CACHE_SECONDS. A feed that fails keeps its last good items."""
    fetcher = fetcher or fetch
    with _lock:
        if not force and _cache['items'] and time.time() - _cache['at'] < CACHE_SECONDS:
            return _cache

        def one(feed):
            name, url = feed
            try:
                return name, parse(name, fetcher(url)), None
            except Exception as e:                       # noqa: BLE001 - any feed problem is reported, never fatal
                return name, None, f'{type(e).__name__}: {e}'[:200]
        with ThreadPoolExecutor(max_workers=len(FEEDS)) as ex:
            results = list(ex.map(one, FEEDS))
        sources = []
        for name, items, err in results:
            if items is not None:
                _cache['by_feed'][name] = items
            sources.append({'name': name, 'ok': err is None, 'items': len(items or _cache['by_feed'].get(name, [])), 'error': err})
        _cache.update(at=time.time(), items=merge(list(_cache['by_feed'].values())), sources=sources)
        return _cache


def reset_cache():
    with _lock:
        _cache.update(at=0.0, items=[], sources=[], by_feed={})
