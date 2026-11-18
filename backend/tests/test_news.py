"""News headlines (backend/app/news.py, /api/v1/news). The feeds are replaced by made-up RSS here: no network."""
import pytest

from backend.app import news as N
from backend.app.routers import news as R


def rss(*items, doctype=''):
    body = ''.join(f'<item><title><![CDATA[{t}]]></title><link>{link}</link><pubDate>{d}</pubDate>'
                   f'<description><![CDATA[{s}]]></description></item>' for t, link, d, s in items)
    return f'<?xml version="1.0"?>{doctype}<rss version="2.0"><channel><title>x</title>{body}</channel></rss>'.encode()


ESPN = rss(("Cavs' Mobley sidelined another 7-10 days", 'https://example.com/a', 'Mon, 16 Nov 2026 19:09:11 EST',
            'Cavaliers forward Evan Mobley will miss at least another week.'),
           ("Grizzlies' Jackson to miss time", 'https://example.com/b', 'Mon, 16 Nov 2026 18:00:00 EST',
            'Grizzlies reserve GG Jackson will miss time.'),
           ('A bad link', 'javascript:alert(1)', 'Mon, 16 Nov 2026 18:00:00 EST', ''))
YAHOO = rss(('Victor Wembanyama named Player of the Week', 'https://example.com/c', 'Tue, 17 Nov 2026 00:34:36 +0000',
             'Another day, another reward for &lt;b&gt;The Alien&lt;/b&gt;.'),
            ("Cavs' Mobley sidelined another 7-10 days", 'https://example.com/a-copy', 'Mon, 16 Nov 2026 20:00:00 EST', 'Same story.'))


def test_parse_reads_cdata_dates_and_entities_and_drops_non_web_links():
    items = N.parse('ESPN', ESPN)
    assert [i['link'] for i in items] == ['https://example.com/a', 'https://example.com/b']       # javascript: link dropped
    assert items[0]['published'] == '2026-11-17T00:09:11+00:00'                                     # EST -> UTC
    y = N.parse('Yahoo', YAHOO)
    assert y[0]['summary'] == 'Another day, another reward for The Alien.'                          # escaped HTML becomes text


def test_parse_refuses_doctype_and_trims_long_summaries():
    with pytest.raises(ValueError):
        N.parse('x', rss(('t', 'https://e.com', '', ''), doctype='<!DOCTYPE rss [<!ENTITY a "b">]>'))
    long = N.parse('x', rss(('t', 'https://e.com', '', 'word ' * 200)))[0]['summary']
    assert len(long) <= N.SUMMARY_CHARS + 1 and long.endswith('…')


def test_merge_keeps_each_story_once_newest_first():
    out = N.merge([N.parse('ESPN', ESPN), N.parse('Yahoo', YAHOO)])
    titles = [i['title'] for i in out]
    assert titles.count("Cavs' Mobley sidelined another 7-10 days") == 1                           # same headline, two feeds
    assert [i['published'] for i in out] == sorted((i['published'] for i in out), reverse=True)


TEAMS = [{'abbr': 'CLE', 'franchise': 'Cleveland Cavaliers', 'team_name': 'Cleveland Cavaliers', 'city': 'Cleveland'},
         {'abbr': 'MEM', 'franchise': 'Memphis Grizzlies', 'team_name': 'Memphis Grizzlies', 'city': 'Memphis'},
         {'abbr': 'SAS', 'franchise': 'San Antonio Spurs', 'team_name': 'San Antonio Spurs', 'city': 'San Antonio'},
         {'abbr': 'LAL', 'franchise': 'Los Angeles Lakers', 'team_name': 'Los Angeles Lakers', 'city': 'Los Angeles'},
         {'abbr': 'LAC', 'franchise': 'Los Angeles Clippers', 'team_name': 'Los Angeles Clippers', 'city': 'Los Angeles'},
         {'abbr': 'MIA', 'franchise': 'Miami Heat', 'team_name': 'Miami Heat', 'city': 'Miami'}]
PLAYERS = [{'player_id': 'mobleev01', 'player': 'Evan Mobley', 'team': 'CLE', 'mp': 32},
           {'player_id': 'jacksgg01', 'player': 'GG Jackson II', 'team': 'MEM', 'mp': 12},
           {'player_id': 'jacksja02', 'player': 'Jaren Jackson Jr.', 'team': 'LAL', 'mp': 30},
           {'player_id': 'wembavi01', 'player': 'Victor Wembanyama', 'team': 'SAS', 'mp': 30},
           {'player_id': 'doncilu01', 'player': 'Luka Dončić', 'team': 'LAL', 'mp': 36},
           {'player_id': 'brownja02', 'player': 'Jaylen Brown', 'team': 'MIA', 'mp': 33}]


@pytest.fixture
def tagger():
    return N.Tagger.build(TEAMS, PLAYERS)


def tags(t, title, summary=''):
    r = t.tag({'title': title, 'summary': summary})
    return sorted(p['player_id'] for p in r['players']), sorted(x['abbr'] for x in r['teams'])


def test_full_names_nicknames_and_unique_surnames(tagger):
    assert tags(tagger, 'Wemby does it again') == (['wembavi01'], ['SAS'])                       # nickname, and his team
    assert tags(tagger, 'Luka Doncic scores 43') == (['doncilu01'], ['LAL'])                     # accents optional
    assert tags(tagger, "Cavs' Mobley out a week") == (['mobleev01'], ['CLE'])                   # surname alone, team nickname
    assert tags(tagger, 'GG Jackson to miss time') == (['jacksgg01'], ['MEM'])                   # full name without "II"


def test_common_surnames_need_their_team_in_the_story(tagger):
    assert tags(tagger, 'Jackson to miss time') == ([], [])                                      # two Jacksons, no team
    assert tags(tagger, "Grizzlies' Jackson to miss time") == (['jacksgg01'], ['MEM'])           # the only Jackson on Memphis
    assert tags(tagger, 'Brown scores 30') == ([], [])                                           # an everyday word alone
    assert tags(tagger, 'Heat beat Brown and company')[1] == ['MIA']


def test_team_names_are_proper_nouns_and_shared_cities_are_ambiguous(tagger):
    assert tags(tagger, 'Turning up the heat in the playoff race') == ([], [])                    # lowercase word, not the team
    assert tags(tagger, 'Los Angeles hosts the All-Star Game') == ([], [])                       # two teams there
    assert tags(tagger, 'Lakers and Clippers split a doubleheader')[1] == ['LAC', 'LAL']


def test_a_failing_feed_keeps_its_last_good_items_and_the_cache_is_shared():
    N.reset_cache()
    calls = []
    good = {N.FEEDS[0][1]: ESPN, N.FEEDS[1][1]: YAHOO, N.FEEDS[2][1]: rss()}

    def fetcher(url):
        calls.append(url)
        return good[url]
    first = N.latest(fetcher=fetcher)
    assert len(calls) == 3 and all(s['ok'] for s in first['sources'])
    N.latest(fetcher=fetcher)
    assert len(calls) == 3                                                    # cached: no refetch within CACHE_SECONDS

    def broken(url):
        raise OSError('down')
    again = N.latest(force=True, fetcher=broken)
    assert not any(s['ok'] for s in again['sources']) and len(again['items']) == len(first['items'])   # last good copy kept
    N.reset_cache()


@pytest.fixture
def fake_feeds(monkeypatch):
    feeds = {N.FEEDS[0][1]: ESPN, N.FEEDS[1][1]: YAHOO, N.FEEDS[2][1]: rss()}
    monkeypatch.setattr(N, 'fetch', lambda url: feeds[url])
    N.reset_cache()
    R._tagger.clear()
    yield
    N.reset_cache()


def test_news_endpoint_filters_by_team_and_player(client, fake_feeds):
    r = client.get('/api/v1/news').json()
    assert {s['name'] for s in r['sources']} == {'ESPN', 'Yahoo Sports', 'CBS Sports'} and len(r['teams']) == 30
    assert all(i['link'].startswith('https://') for i in r['items'])
    cle = client.get('/api/v1/news?team=CLE').json()['items']
    assert cle and all(any(t['abbr'] == 'CLE' for t in i['teams']) for i in cle)
    wemby = client.get('/api/v1/news?player=wembavi01').json()
    assert [i['title'] for i in wemby['items']] == ['Victor Wembanyama named Player of the Week']
    assert any(p['player_id'] == 'wembavi01' for p in wemby['players_in_news'])


def test_news_endpoint_rejects_unknown_or_retired(client, fake_feeds):
    assert client.get('/api/v1/news?team=XYZ').status_code == 404
    assert client.get('/api/v1/news?player=jordami01').status_code == 404          # retired: no current-season row
