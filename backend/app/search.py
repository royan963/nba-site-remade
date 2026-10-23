"""Natural-language search: turn a question like "best rebounding guards of the
90s" into structured filters. Rule-based and deterministic (no AI service),
so every interpretation can be shown back to the user as removable filters.

parse(text, teams, archetypes, latest_season) -> Query
"""
import re
from dataclasses import dataclass, field

# ---- vocabulary ---------------------------------------------------------------------
# (key, label, phrases). Longer phrases are matched first.
STATS = [
    ('x3p_pct', '3-point %', ['3pt percentage', '3pt shooting', '3pt shooters', '3pt', 'three point shooters', 'three-point shooters', '3 point shooters', '3-point shooters', '3pt shooters',
                              'three point shooting', 'three-point shooting', '3-point shooting', '3 point percentage', 'three point percentage',
                              '3-point percentage', '3p%', '3pt%', 'from three', 'from 3', 'shooters', 'shooting']),
    ('x3pm', '3-pointers made per game', ['threes', '3-pointers', '3 pointers', 'three-pointers', 'three pointers', '3s']),
    ('dbpm', 'Defensive BPM', ['defensive players', 'defensive player', 'defenders', 'defender', 'defense', 'defensive', 'stoppers', 'dbpm']),
    ('height', 'Height', ['tallest', 'shortest', 'height', 'tall', 'short']),
    ('age', 'Age', ['youngest', 'oldest']),
    ('titles', 'Championships', ['championships', 'championship', 'rings', 'titles', 'title']),
    ('salary', 'Salary', ['highest paid', 'best paid', 'most paid', 'salaries', 'salary', 'paid', 'contracts', 'contract', 'earnings',
                          'expensive', 'money']),
    ('ft_pct', 'Free throw %', ['free throw shooters', 'free-throw shooters', 'free throw percentage', 'free throw shooting', 'ft%', 'free throws']),
    ('fg_pct', 'Field goal %', ['field goal percentage', 'field goal %', 'fg%', 'field goals']),
    ('ts_pct', 'True shooting %', ['true shooting', 'ts%', 'efficient', 'efficiency']),
    ('ws', 'Win Shares', ['win shares', 'winshares']),
    ('bpm', 'Box Plus/Minus', ['box plus minus', 'box plus/minus', 'plus minus', 'plus-minus', 'bpm']),
    ('vorp', 'VORP', ['vorp', 'value over replacement']),
    ('per', 'PER', ['player efficiency rating', 'per']),
    ('blk', 'Blocks per game', ['shot blockers', 'shot blocking', 'shot-blocking', 'shot-blockers', 'blockers', 'blocks', 'blocked shots', 'bpg']),
    ('stl', 'Steals per game', ['steals', 'thieves', 'ball hawks', 'spg']),
    ('ast', 'Assists per game', ['assists', 'passers', 'passing', 'playmakers', 'playmaking', 'apg', 'dimes']),
    ('trb', 'Rebounds per game', ['rebounding', 'rebounders', 'rebounds', 'boards', 'rpg', 'glass']),
    ('pts', 'Points per game', ['scoring', 'scorers', 'points', 'ppg', 'score', 'scorer', 'scored']),
    ('mp', 'Minutes per game', ['minutes', 'mpg']),
    ('g', 'Games played', ['games played', 'iron men', 'durable']),
]
STAT_LABEL = {k: label for k, label, _ in STATS}
THRESHOLD_WORDS = {'pts': ['points', 'pts', 'ppg', 'point'], 'trb': ['rebounds', 'reb', 'rpg', 'boards', 'rebound'],
                   'ast': ['assists', 'ast', 'apg', 'assist'], 'stl': ['steals', 'stl', 'spg', 'steal'],
                   'blk': ['blocks', 'blk', 'bpg', 'block'], 'x3pm': ['threes', '3s', '3-pointers', 'three-pointers', '3pm'],
                   'mp': ['minutes', 'mpg'], 'g': ['games']}

POSITIONS = [
    ('point guards', {'PG'}), ('point guard', {'PG'}), ('shooting guards', {'SG'}), ('shooting guard', {'SG'}),
    ('small forwards', {'SF'}), ('small forward', {'SF'}), ('power forwards', {'PF'}), ('power forward', {'PF'}),
    ('big men', {'PF', 'C'}), ('big man', {'PF', 'C'}), ('bigs', {'PF', 'C'}),
    ('guards', {'PG', 'SG', 'G'}), ('guard', {'PG', 'SG', 'G'}), ('wings', {'SG', 'SF'}), ('wing', {'SG', 'SF'}),
    ('forwards', {'SF', 'PF', 'F'}), ('forward', {'SF', 'PF', 'F'}), ('centers', {'C'}), ('center', {'C'}),
    ('centres', {'C'}), ('centre', {'C'}),
]
DECADE_WORDS = {'forties': 1940, 'fifties': 1950, 'sixties': 1960, 'seventies': 1970, 'eighties': 1980, 'nineties': 1990,
                'two thousands': 2000, 'aughts': 2000, 'twenty tens': 2010, 'teens': 2010, 'twenties': 2020}
CAREER_WORDS = ['all-time', 'all time', 'of all time', 'career', 'careers', 'in history', 'in nba history', 'history', 'ever']
# "average", "per game", "ppg": the question wants the per-game number, not a career total
PER_GAME_RE = re.compile(r'\b(?:averag(?:e|ed|es|ing)|avg|per game|a game|per night|each game|ppg|rpg|apg|spg|bpg|mpg)\b')
# a titles question is about a team unless it asks who/which player or for a ranking
TITLE_RANKING_RE = re.compile(r'\b(?:who|whom|which|players?|most|leaders?|leading|top|best)\b')
# questions about a team itself (its record, payroll, best seasons) rather than its players
RECORD_RE = re.compile(r'\b(?:records?|wins?|won|losses|loss|lost|win-loss|win loss|standings|winning percentage|win percentage)\b|\bhow many games\b')
PAYROLL_RE = re.compile(r'\b(?:payroll|team salary|salary cap|cap space)\b')
BEST_TEAM_RE = re.compile(r'\b(?:best|worst|greatest|top)\s+teams?\b|\b(?:best|worst|greatest)\s+(?:seasons?|records?)\b|\b(?:most|fewest)\s+wins\b')
GAME_WORDS = ['in a single game', 'in one game', 'in a game', 'single game', 'single-game', 'one game', 'performances', 'performance']
GAME_PATTERN = r'\b(?:in|during)\s+(?:a|one|any|an)\s+(?:single\s+|playoff\s+|postseason\s+|regular[- ]season\s+)?game\b'
PLAYOFF_WORDS = ['in the playoffs', 'in playoff history', 'playoff history', 'postseason', 'playoffs', 'playoff']
CAREER_ONLY = {'height', 'titles'}                 # attributes of a player, not of a season
ASCENDING = {'shortest', 'youngest'}               # superlatives that rank low to high
SEASON_WORDS = ['single season', 'single-season', 'in a season', 'in one season', 'season']
WORST = ['worst', 'lowest', 'fewest', 'least']
# season awards: (pattern, key, label). Order matters: 'finals mvp' before 'mvp', 'rookie of the year' before 'rookie'.
AWARDS = [(r'\bfinals mvps?\b', 'finals_mvp', 'Finals MVP'),
          (r'\bdefensive players? of the year\b|\bdpoys?\b', 'dpoy', 'Defensive Player of the Year'),
          (r'\brookies? of the year\b|\broys?\b', 'roy', 'Rookie of the Year'),
          (r'\bsixth m[ae]n(?: of the year)?\b|\b6th m[ae]n\b|\b6moy\b', 'smoy', 'Sixth Man of the Year'),
          (r'\bmost improved(?: players?)?(?: of the year)?\b|\bmips?\b', 'mip', 'Most Improved Player'),
          (r'\bclutch players? of the year\b|\bclutch players?\b', 'clutch', 'Clutch Player of the Year')]
STOPWORDS = set('''the a an of in by with who which that players player nba best top most greatest highest leading
    and or for from to at on season seasons year years list show me find give all what were was is are have has had did do
    averaging averaged average avg per game games' good great elite during era time any how many much does won win wins
    winners winner winning stats statistics numbers led lead leads leaders leader league ranked rank ranking got get
    made make makes shoot shoots shot hit hits his her their career's vs versus compare compared better than'''.split())


@dataclass
class Filter:
    kind: str           # stat | position | archetype | seasons | age | rookie | team | min | honor | scope | limit
    label: str
    value: object = None
    mins: list = field(default_factory=list)       # for 'min' filters: the (stat, op, value) entries it added
    index: int | None = None                       # position in the original parse (stable across removals)


@dataclass
class Query:
    text: str
    scope: str = 'seasons'                  # 'seasons' or 'careers'
    stat: str | None = None
    order: str = 'desc'
    limit: int = 25
    positions: set | None = None
    archetype: str | None = None
    season_from: int | None = None
    season_to: int | None = None
    age_min: int | None = None
    age_max: int | None = None
    rookie: bool = False
    sophomore: bool = False
    teams: list = field(default_factory=list)      # team names (from the teams vocabulary)
    minimums: list = field(default_factory=list)   # (stat, op, value)
    honors: set = field(default_factory=set)       # mvp, all_star, hof, all_nba, finals_mvp, dpoy, roy, smoy, mip, clutch
    playoffs: bool = False                         # playoff stats instead of the regular season
    player_ids: list = field(default_factory=list) # questions about named players (set by the router)
    filters: list = field(default_factory=list)    # what was understood, for display
    ignored: list = field(default_factory=list)    # words that didn't match anything
    stat_given: bool = False                       # False when we fell back to ranking by Win Shares
    superlative: bool = False                      # "best", "greatest", "top": rank even with no stat named
    per_game: bool = False                         # "average", "per game", "ppg": the per-game number, not a total
    per_game_used: bool = False                    # set by the router when a career query was ranked per game
    team_titles: bool = False                      # "how many rings do the Lakers have": a question about the team
    team_intent: str | None = None                 # record | best | payroll: a question about a team, not its players
    team_by_wins: bool = False                     # "most wins": rank team seasons by wins instead of win percentage

    @property
    def understood(self) -> bool:
        return self.stat_given or self.superlative or any(f.kind not in ('limit', 'scope', 'stat') for f in self.filters)


def _norm(text: str) -> str:
    t = text.lower().replace('\u2019', "'").replace('\u2018', "'").replace('\u2013', '-').replace('\u2014', '-')
    t = re.sub(r'[?!.,;:"]', ' ', t)
    t = re.sub(r'\b(?:3|three)[- ]?(?:point|pt)(?!er)s?\b', '3pt', t)          # '3 point percentage' isn't '3+ points'
    return re.sub(r'\s+', ' ', t).strip()


class _Text:
    """The lowercased query with matched spans blanked out as they're consumed."""
    def __init__(self, text):
        self.s = ' ' + text + ' '

    def take(self, pattern, flags=0):
        m = re.search(pattern, self.s, flags)
        if m:
            self.s = self.s[:m.start()] + ' ' * (m.end() - m.start()) + self.s[m.end():]
        return m

    def take_phrase(self, phrase):
        return self.take(r'(?<![\w-])' + re.escape(phrase) + r'(?![\w-])')

    def has(self, phrase):
        return re.search(r'(?<![\w-])' + re.escape(phrase) + r'(?![\w-])', self.s) is not None

    def leftovers(self):
        return [w for w in re.findall(r"[a-z0-9'%+/-]+", self.s) if w not in STOPWORDS and len(w) > 1]


def _decade(two_or_four: str) -> int:
    n = int(two_or_four)
    if n >= 100:
        return n
    return 1900 + n if n >= 40 else 2000 + n


def _season_label(a, b):
    if a == b:
        return f'{a - 1}-{str(a)[2:]} season'
    if a is None:
        return f'through {b}'
    if b is None:
        return f'{a} on'
    return f'{a}\u2013{b}'


def parse(text: str, teams: dict | None = None, archetypes: dict | None = None, latest_season: int = 2026) -> Query:
    """teams: alias -> list of team names ("celtics" -> ["Boston Celtics"]).
    archetypes: phrase -> archetype key ("stretch bigs" -> "stretch-big")."""
    q = Query(text=text)
    t = _Text(_norm(text))
    q.superlative = re.search(r'\b(best|greatest|top|most valuable|worst)\b', t.s) is not None
    q.per_game = PER_GAME_RE.search(t.s) is not None

    # how many
    m = t.take(r'\b(?:top|best|first)\s+(\d{1,3})\b') or t.take(r'\b(\d{1,3})\s+(?:best|top|greatest|highest|most)\b')
    if m:
        q.limit = max(1, min(100, int(m.group(1))))
        q.filters.append(Filter('limit', f'top {q.limit}', q.limit))

    # single games, playoffs, careers vs seasons
    if t.take(GAME_PATTERN) or any(t.has(w) for w in GAME_WORDS) or re.search(r'\b\d{2,3}[- ]point games?\b', t.s):
        q.scope = 'games'
        t.s = re.sub(r'(?<=point) games?\b', '', t.s)
        if re.search(r'\bplayoff game|\bpostseason game', text.lower()):
            t.s = t.s + ' playoffs '
        for w in GAME_WORDS:
            t.take_phrase(w)
        q.filters.append(Filter('scope', 'single games'))
    if any(t.has(w) for w in PLAYOFF_WORDS):
        q.playoffs = True
        history = t.has('playoff history')
        for w in PLAYOFF_WORDS:
            t.take_phrase(w)
        if history and q.scope != 'games':
            q.scope = 'careers'
            q.filters.append(Filter('scope', 'careers'))
        q.filters.append(Filter('playoffs', 'playoffs'))
    # 'season' beats 'ever': "highest scoring season ever" asks about seasons
    single = any(t.has(w) for w in ('single season', 'single-season', 'in a season', 'in one season', 'season')) and not t.has('career')
    if single:
        t.take_phrase('ever')
    # season awards here, before 'rookie' and 'mvp' are read on their own ('rookie of the year', 'finals mvp')
    for pattern, key, label in AWARDS:
        if t.take(pattern):
            q.honors.add(key)
            q.filters.append(Filter('honor', label, key))
    if q.scope == 'seasons' and not single and any(t.has(w) for w in CAREER_WORDS):
        q.scope = 'careers'
        for w in CAREER_WORDS:
            t.take_phrase(w)
        q.filters.append(Filter('scope', 'careers'))
    for w in ('single season', 'single-season', 'in a season', 'in one season'):
        t.take_phrase(w)

    if any(t.take_phrase(w) for w in WORST):
        q.order = 'asc'
    if t.take(r'\bwho led the league\b|\bled the league\b|\bleague leaders?\b'):
        q.limit = 1 if q.limit == 25 else q.limit
        q.superlative = True

    # statlines: 50/40/90, 25/10/5, 25 and 10, triple-double
    m = t.take(r'\b(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{2,3})\b')
    if m:
        a, b, c = (int(x) for x in m.groups())
        if a >= 35 and c >= 60:          # shooting splits
            for stat, v in (('fg_pct', a), ('x3p_pct', b), ('ft_pct', c)):
                q.minimums.append((stat, '>=', v / 100))
            q.filters.append(Filter('min', f'{a}/{b}/{c} shooting (FG/3P/FT)', mins=q.minimums[-3:]))
        else:
            for stat, v in (('pts', a), ('trb', b), ('ast', c)):
                q.minimums.append((stat, '>=', v))
            q.filters.append(Filter('min', f'{a}+ pts, {b}+ reb, {c}+ ast', mins=q.minimums[-3:]))
    if t.take(r'\btriple[- ]doubles?\b'):
        q.minimums += [('pts', '>=', 10), ('trb', '>=', 10), ('ast', '>=', 10)]
        q.filters.append(Filter('min', 'triple-double average (10/10/10)', mins=q.minimums[-3:]))
    if t.take(r'\bdouble[- ]doubles?\b'):
        q.minimums += [('pts', '>=', 10), ('trb', '>=', 10)]
        q.filters.append(Filter('min', 'double-double average (10 pts, 10 reb)', mins=q.minimums[-2:]))

    # thresholds with units: "30 points", "at least 10 rebounds", "under 20 minutes", "40% from three"
    unit = '|'.join(sorted({re.escape(w) for ws in THRESHOLD_WORDS.values() for w in ws}, key=len, reverse=True))
    pat = (r'\b(at least|more than|over|above|under|below|fewer than|less than)?\s*(\d+(?:\.\d+)?)\s*(\+|or more|plus)?\s*'
           r'(?:per game\s*)?(' + unit + r')\b(?:\s*(?:per game|a game))?')
    while True:
        m = t.take(pat)
        if not m:
            break
        word, num, _, u = m.groups()
        stat = next(k for k, ws in THRESHOLD_WORDS.items() if u in ws)
        op = '<' if word in ('under', 'below', 'fewer than', 'less than') else '>='
        q.minimums.append((stat, op, float(num)))
        n = num.rstrip('0').rstrip('.') if '.' in num else num
        q.filters.append(Filter('min', f"{'under ' + n if op == '<' else n + '+'} {STAT_LABEL[stat].split(' per')[0].lower()}",
                                mins=q.minimums[-1:]))
    m = t.take(r'\b(\d{2})\s*(?:%|percent)\s*(?:from three|from 3|on threes|3p|3pt)\b')
    if m:
        q.minimums.append(('x3p_pct', '>=', int(m.group(1)) / 100))
        q.filters.append(Filter('min', f'{m.group(1)}%+ from three', mins=q.minimums[-1:]))
    m = t.take(r'\b(\d{1,2})\s*(?:and|&)\s*(\d{1,2})\b(?!\s*(?:-|/)?\s*\d)')
    if m:                                 # "25 and 10" = points and rebounds
        q.minimums += [('pts', '>=', int(m.group(1))), ('trb', '>=', int(m.group(2)))]
        q.filters.append(Filter('min', f'{m.group(1)}+ pts and {m.group(2)}+ reb', mins=q.minimums[-2:]))

    # seasons / eras
    m = (t.take(r'\b(?:between|from)\s+(\d{4})\s+(?:and|to|-|through)\s+(\d{4})\b') or t.take(r'\b(\d{4})\s*(?:-|to|through)\s*(\d{4})\b'))
    if m:
        q.season_from, q.season_to = sorted(int(x) for x in m.groups())
    m = None if q.season_from else t.take(r"\b(?:the\s+)?'?(\d{2}|\d{4})'?s\s+(?:and|&|to|through|-)\s+(?:the\s+)?'?(\d{2}|\d{4})'?s\b")
    if m:
        q.season_from, q.season_to = _decade(m.group(1)), _decade(m.group(2)) + 9
    m = None if q.season_from else t.take(r"\b(?:the\s+)?'?(\d0|\d{3}0)'?s\b")
    if m:
        d = _decade(m.group(1))
        q.season_from, q.season_to = d, d + 9
    for word, d in DECADE_WORDS.items():
        if not q.season_from and t.take_phrase(word):
            q.season_from, q.season_to = d, d + 9
    m = None if q.season_from else t.take(r'\b(\d{4})\s*-\s*(\d{2})\b')        # 2015-16 season
    if m:
        q.season_from = q.season_to = int(m.group(1)) + 1
    m = t.take(r'\b(?:since|after|from)\s+(\d{4})\b')
    if m:
        q.season_from = int(m.group(1)) + (1 if 'after' in m.group(0) else 0)
    m = t.take(r'\b(?:before|prior to|until)\s+(\d{4})\b')
    if m:
        q.season_to = int(m.group(1)) - 1
    m = t.take(r'\blast\s+(\d{1,2})\s+(?:seasons|years)\b')
    if m:
        q.season_from, q.season_to = latest_season - int(m.group(1)) + 1, latest_season
    if t.take(r'\b(?:this|last|current|latest)\s+season\b') or t.take(r'\bthis year\b'):
        q.season_from = q.season_to = latest_season
    m = None if (q.season_from or q.season_to) else t.take(r'\b(?:in\s+)?(19[4-9]\d|20[0-3]\d)\b')
    if m:
        q.season_from = q.season_to = int(m.group(1))
    if q.season_from or q.season_to:
        q.filters.append(Filter('seasons', _season_label(q.season_from, q.season_to)))

    # age, rookies
    m = t.take(r'\b(?:under|younger than|below)\s+(?:age\s+)?(\d{2})\b')
    if m:
        q.age_max = int(m.group(1)) - 1
    m = t.take(r'\b(\d{2})\s+(?:or|and)\s+(?:younger|under)\b') or t.take(r'\bage\s+(\d{2})\s+(?:or|and)\s+(?:younger|under)\b')
    if m:
        q.age_max = int(m.group(1))
    m = t.take(r'\b(?:over|older than|above)\s+(?:age\s+)?(\d{2})\b(?!\s*(?:points|rebounds|assists|minutes|games))')
    if m:
        q.age_min = int(m.group(1)) + 1
    m = t.take(r'\b(\d{2})\s+(?:or|and)\s+(?:older|over|up)\b')
    if m:
        q.age_min = int(m.group(1))
    m = t.take(r'\b(?:at\s+)?age\s+(\d{2})\b') or t.take(r'\b(\d{2})[- ]year[- ]olds?\b')
    if m:
        q.age_min = q.age_max = int(m.group(1))
    if t.take(r'\bteenagers?\b|\bteens?\b'):
        q.age_max = 19
    if q.age_max is None and t.take(r'\byoung\b(?! *(?:est|er))'):
        q.age_max = 24
    if q.age_min is not None or q.age_max is not None:
        lab = (f'age {q.age_min}' if q.age_min == q.age_max else
               f'age {q.age_max} or younger' if q.age_min is None else
               f'age {q.age_min} or older' if q.age_max is None else f'age {q.age_min}\u2013{q.age_max}')
        q.filters.append(Filter('age', lab))
    if t.take(r'\brookies?\b|\bfirst[- ]year\b'):
        q.rookie = True
        q.filters.append(Filter('rookie', 'rookie seasons'))
    if t.take(r'\bsophomores?\b|\bsecond[- ]year\b'):
        q.sophomore = True
        q.filters.append(Filter('rookie', 'second seasons'))

    # honors
    for pattern, key, label in ((r'\bmvps?\b', 'mvp', 'MVP that season'), (r'\ball[- ]stars?\b', 'all_star', 'All-Star that season'),
                                (r'\bhall of famers?\b|\bhall of fame\b|\bhof\b', 'hof', 'Hall of Famers'),
                                (r'\ball[- ]nba\b', 'all_nba', 'All-NBA that season')):
        if t.take(pattern):
            q.honors.add(key)
            q.filters.append(Filter('honor', label if q.scope == 'seasons' or key == 'hof' else label.replace(' that season', ' (ever)'), key))

    # playing-style archetypes (before positions: "stretch bigs" isn't just "bigs")
    for phrase, key in sorted((archetypes or {}).items(), key=lambda kv: -len(kv[0])):
        if t.take_phrase(phrase):
            q.archetype = key
            q.filters.append(Filter('archetype', phrase.rstrip('s').title() if not phrase.endswith('ss') else phrase.title(), key))
            break

    # teams
    for alias, names in sorted((teams or {}).items(), key=lambda kv: -len(kv[0])):
        if t.take_phrase(alias):
            q.teams = names
            q.filters.append(Filter('team', alias.title() if not alias.isupper() else alias))
            break

    for phrase, pos in POSITIONS:
        if t.take_phrase(phrase):
            q.positions = pos
            q.filters.append(Filter('position', phrase if phrase.endswith('s') or phrase.endswith('men') else phrase + 's'))
            break

    # what to rank by ("efficient scorers" = true shooting among real scorers)
    if t.has('efficient') and any(t.has(w) for w in ('scorers', 'scoring', 'scorer')):
        q.minimums.append(('pts', '>=', 15))
        q.filters.append(Filter('min', '15+ points', mins=q.minimums[-1:]))
    # longest phrase wins across all stats ("free throw shooters" before "shooters")
    for phrase, key in sorted(((p, k) for k, _, ps in STATS for p in ps), key=lambda pk: -len(pk[0])):
        if t.take_phrase(phrase) and q.stat is None:
            q.stat, q.stat_given = key, True
            if phrase in ASCENDING:
                q.order = 'asc'
    if q.stat in CAREER_ONLY and q.scope == 'seasons':
        q.scope = 'careers'
    if q.stat == 'age' and q.scope == 'careers':
        q.scope = 'seasons'
    if q.stat is None:
        q.stat = q.minimums[0][0] if q.minimums and q.minimums[0][0] not in ('fg_pct', 'x3p_pct', 'ft_pct') else 'ws'
    q.filters.insert(0, Filter('stat', ('lowest ' if q.order == 'asc' else '') + STAT_LABEL[q.stat], q.stat))

    if q.stat == 'titles' and q.teams and not TITLE_RANKING_RE.search(text.lower()):
        q.team_titles = True
    if not q.stat_given and not q.team_titles:
        low = text.lower()
        best = BEST_TEAM_RE.search(low)
        if q.teams and PAYROLL_RE.search(low):
            q.team_intent = 'payroll'
        elif best and (q.teams or any(w in best.group(0) for w in ('team', 'record', 'wins'))):
            q.team_intent = 'best'
            q.team_by_wins = 'wins' in best.group(0)
        elif q.teams and RECORD_RE.search(low):
            q.team_intent = 'record'
    q.ignored = t.leftovers()
    return q


def drop_filters(q: Query, indexes) -> Query:
    """Undo the filters at these positions in q.filters (the UI's remove buttons).
    Each remaining filter keeps its original position in `index`, so the UI can
    remove more filters later without the positions shifting."""
    for i, f in enumerate(q.filters):
        f.index = i
    for i in sorted({int(i) for i in indexes if 0 <= int(i) < len(q.filters)}, reverse=True):
        f = q.filters.pop(i)
        if f.kind == 'position':
            q.positions = None
        elif f.kind == 'archetype':
            q.archetype = None
        elif f.kind == 'seasons':
            q.season_from = q.season_to = None
        elif f.kind == 'age':
            q.age_min = q.age_max = None
        elif f.kind == 'rookie':
            q.rookie = q.sophomore = False
        elif f.kind == 'team':
            q.teams = []
        elif f.kind == 'honor':
            q.honors.discard(f.value)
        elif f.kind == 'min':
            q.minimums = [m for m in q.minimums if not any(m is x for x in f.mins)]
        elif f.kind == 'limit':
            q.limit = 25
        elif f.kind == 'scope':
            q.scope = 'seasons'
        elif f.kind == 'playoffs':
            q.playoffs = False
        elif f.kind == 'player':
            q.player_ids = []
        elif f.kind == 'stat':
            q.stat, q.order = 'ws', 'desc'
            q.filters.insert(0, Filter('stat', STAT_LABEL['ws'], 'ws', index=None))
    return q
