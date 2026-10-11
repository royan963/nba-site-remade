"""Maps every team-name string in the dataset to a franchise lineage, with a
city (and coordinates) for the season range it applies to.
Defunct/folded teams get their own standalone lineage."""

CITY_COORDS = {
    'Boston': (42.3662, -71.0621), 'New York': (40.7505, -73.9934), 'Brooklyn': (40.6826, -73.9754),
    'Philadelphia': (39.9012, -75.1720), 'Syracuse': (43.0481, -76.1474), 'Chicago': (41.8807, -87.6742),
    'Cleveland': (41.4965, -81.6882), 'Detroit': (42.3411, -83.0553), 'Fort Wayne': (41.0793, -85.1394),
    'Milwaukee': (43.0451, -87.9173), 'Minneapolis': (44.9795, -93.2761), 'Indianapolis': (39.7640, -86.1555),
    'Rochester': (43.1656, -77.6088), 'Cincinnati': (39.0997, -84.5121), 'Kansas City': (39.0997, -94.5786),
    'Omaha': (41.2565, -95.9345), 'Sacramento': (38.6493, -121.5188), 'St. Louis': (38.6493, -90.2614),
    'Atlanta': (33.7573, -84.3963), 'Tri-Cities': (41.5067, -90.5151), 'Baltimore': (39.2789, -76.6217),
    'Washington': (38.8981, -77.0209), 'Capital (DC)': (38.8981, -77.0209), 'Buffalo': (42.8750, -78.8773),
    'San Diego': (32.7073, -117.1566), 'Houston': (29.7508, -95.3621), 'Los Angeles': (34.0430, -118.2673),
    'San Francisco': (37.7680, -122.3877), 'Oakland': (37.7503, -122.2030), 'San Francisco Bay': (37.7680, -122.3877),
    'Golden State (SF Bay)': (37.7680, -122.3877), 'Seattle': (47.6221, -122.3539),
    'Oklahoma City': (35.4634, -97.5151), 'Portland': (45.5316, -122.6668), 'Phoenix': (33.4457, -112.0712),
    'San Antonio': (29.4270, -98.4375), 'Dallas': (32.7905, -96.8104), 'Denver': (39.7487, -105.0077),
    'Utah (Salt Lake City)': (40.7683, -111.9011), 'New Orleans': (29.9490, -90.0821),
    'Charlotte': (35.2251, -80.8392), 'Miami': (25.7814, -80.1870), 'Orlando': (28.5392, -81.3839),
    'Memphis': (35.1382, -90.0505), 'Vancouver': (49.2778, -123.1086), 'Toronto': (43.6435, -79.3791),
    'Minnesota (Mpls)': (44.9795, -93.2761), 'Indiana (Indianapolis)': (39.7640, -86.1555),
    'New Jersey': (40.7308, -74.1724), 'Providence': (41.8240, -71.4128), 'Pittsburgh': (40.4396, -79.9956),
    'Sheboygan': (43.7508, -87.7145), 'Waterloo': (42.4928, -92.3426), 'Anderson': (40.1053, -85.6803),
}

def _m(franchise, city, current, status='active'):
    return dict(franchise=franchise, city=city, current=current, status=status)

TEAM_META = {
    'Boston Celtics': _m('Boston Celtics', 'Boston', 'Boston Celtics'),
    'New York Knicks': _m('New York Knicks', 'New York', 'New York Knicks'),
    # 76ers: Syracuse Nationals -> Philadelphia 76ers
    'Syracuse Nationals': _m('Philadelphia 76ers', 'Syracuse', 'Philadelphia 76ers'),
    'Philadelphia 76ers': _m('Philadelphia 76ers', 'Philadelphia', 'Philadelphia 76ers'),
    # Warriors: Philadelphia -> San Francisco -> Golden State
    'Philadelphia Warriors': _m('Golden State Warriors', 'Philadelphia', 'Golden State Warriors'),
    'San Francisco Warriors': _m('Golden State Warriors', 'San Francisco', 'Golden State Warriors'),
    'Golden State Warriors': _m('Golden State Warriors', 'San Francisco Bay', 'Golden State Warriors'),
    # Pistons: Fort Wayne -> Detroit
    'Fort Wayne Pistons': _m('Detroit Pistons', 'Fort Wayne', 'Detroit Pistons'),
    'Detroit Pistons': _m('Detroit Pistons', 'Detroit', 'Detroit Pistons'),
    # Lakers: Minneapolis -> Los Angeles
    'Minneapolis Lakers': _m('Los Angeles Lakers', 'Minneapolis', 'Los Angeles Lakers'),
    'Los Angeles Lakers': _m('Los Angeles Lakers', 'Los Angeles', 'Los Angeles Lakers'),
    # Hawks: Tri-Cities -> Milwaukee -> St. Louis -> Atlanta
    'Tri-Cities Blackhawks': _m('Atlanta Hawks', 'Tri-Cities', 'Atlanta Hawks'),
    'Milwaukee Hawks': _m('Atlanta Hawks', 'Milwaukee', 'Atlanta Hawks'),
    'St. Louis Hawks': _m('Atlanta Hawks', 'St. Louis', 'Atlanta Hawks'),
    'Atlanta Hawks': _m('Atlanta Hawks', 'Atlanta', 'Atlanta Hawks'),
    # Kings: Rochester -> Cincinnati -> Kansas City(-Omaha) -> Sacramento
    'Rochester Royals': _m('Sacramento Kings', 'Rochester', 'Sacramento Kings'),
    'Cincinnati Royals': _m('Sacramento Kings', 'Cincinnati', 'Sacramento Kings'),
    'Kansas City-Omaha Kings': _m('Sacramento Kings', 'Kansas City', 'Sacramento Kings'),
    'Kansas City Kings': _m('Sacramento Kings', 'Kansas City', 'Sacramento Kings'),
    'Sacramento Kings': _m('Sacramento Kings', 'Sacramento', 'Sacramento Kings'),
    # Wizards: Chicago Packers/Zephyrs -> Baltimore ('63-73) -> Capital -> Washington.
    # NOTE 'Baltimore Bullets' covers TWO franchises; see baltimore_bullets_meta().
    'Chicago Packers': _m('Washington Wizards', 'Chicago', 'Washington Wizards'),
    'Chicago Zephyrs': _m('Washington Wizards', 'Chicago', 'Washington Wizards'),
    'Capital Bullets': _m('Washington Wizards', 'Capital (DC)', 'Washington Wizards'),
    'Washington Bullets': _m('Washington Wizards', 'Washington', 'Washington Wizards'),
    'Washington Wizards': _m('Washington Wizards', 'Washington', 'Washington Wizards'),
    # Rockets: San Diego -> Houston
    'San Diego Rockets': _m('Houston Rockets', 'San Diego', 'Houston Rockets'),
    'Houston Rockets': _m('Houston Rockets', 'Houston', 'Houston Rockets'),
    # Clippers: Buffalo -> San Diego -> Los Angeles
    'Buffalo Braves': _m('Los Angeles Clippers', 'Buffalo', 'Los Angeles Clippers'),
    'San Diego Clippers': _m('Los Angeles Clippers', 'San Diego', 'Los Angeles Clippers'),
    'Los Angeles Clippers': _m('Los Angeles Clippers', 'Los Angeles', 'Los Angeles Clippers'),
    # Jazz: New Orleans -> Utah
    'New Orleans Jazz': _m('Utah Jazz', 'New Orleans', 'Utah Jazz'),
    'Utah Jazz': _m('Utah Jazz', 'Utah (Salt Lake City)', 'Utah Jazz'),
    # Nets: New York -> New Jersey -> Brooklyn
    'New York Nets': _m('Brooklyn Nets', 'New York', 'Brooklyn Nets'),
    'New Jersey Nets': _m('Brooklyn Nets', 'New Jersey', 'Brooklyn Nets'),
    'Brooklyn Nets': _m('Brooklyn Nets', 'Brooklyn', 'Brooklyn Nets'),
    # Thunder: Seattle -> Oklahoma City
    'Seattle SuperSonics': _m('Oklahoma City Thunder', 'Seattle', 'Oklahoma City Thunder'),
    'Oklahoma City Thunder': _m('Oklahoma City Thunder', 'Oklahoma City', 'Oklahoma City Thunder'),
    # Pelicans lineage (2003+ New Orleans Hornets). The 1988-2002 Charlotte Hornets
    # history belongs to the current Charlotte Hornets (Bobcats) franchise per the NBA.
    'New Orleans Hornets': _m('New Orleans Pelicans', 'New Orleans', 'New Orleans Pelicans'),
    'New Orleans/Oklahoma City Hornets': _m('New Orleans Pelicans', 'Oklahoma City', 'New Orleans Pelicans'),
    'New Orleans Pelicans': _m('New Orleans Pelicans', 'New Orleans', 'New Orleans Pelicans'),
    'Charlotte Bobcats': _m('Charlotte Hornets', 'Charlotte', 'Charlotte Hornets'),
    'Charlotte Hornets': _m('Charlotte Hornets', 'Charlotte', 'Charlotte Hornets'),
    # Grizzlies: Vancouver -> Memphis
    'Vancouver Grizzlies': _m('Memphis Grizzlies', 'Vancouver', 'Memphis Grizzlies'),
    'Memphis Grizzlies': _m('Memphis Grizzlies', 'Memphis', 'Memphis Grizzlies'),
    # Stable franchises
    'Chicago Bulls': _m('Chicago Bulls', 'Chicago', 'Chicago Bulls'),
    'Cleveland Cavaliers': _m('Cleveland Cavaliers', 'Cleveland', 'Cleveland Cavaliers'),
    'Dallas Mavericks': _m('Dallas Mavericks', 'Dallas', 'Dallas Mavericks'),
    'Denver Nuggets': _m('Denver Nuggets', 'Denver', 'Denver Nuggets'),
    'Indiana Pacers': _m('Indiana Pacers', 'Indiana (Indianapolis)', 'Indiana Pacers'),
    'Miami Heat': _m('Miami Heat', 'Miami', 'Miami Heat'),
    'Milwaukee Bucks': _m('Milwaukee Bucks', 'Milwaukee', 'Milwaukee Bucks'),
    'Minnesota Timberwolves': _m('Minnesota Timberwolves', 'Minnesota (Mpls)', 'Minnesota Timberwolves'),
    'Orlando Magic': _m('Orlando Magic', 'Orlando', 'Orlando Magic'),
    'Phoenix Suns': _m('Phoenix Suns', 'Phoenix', 'Phoenix Suns'),
    'Portland Trail Blazers': _m('Portland Trail Blazers', 'Portland', 'Portland Trail Blazers'),
    'San Antonio Spurs': _m('San Antonio Spurs', 'San Antonio', 'San Antonio Spurs'),
    'Toronto Raptors': _m('Toronto Raptors', 'Toronto', 'Toronto Raptors'),
    # Defunct teams
    'Anderson Packers': _m('Anderson Packers', 'Anderson', None, 'defunct'),
    'Chicago Stags': _m('Chicago Stags', 'Chicago', None, 'defunct'),
    'Cleveland Rebels': _m('Cleveland Rebels', 'Cleveland', None, 'defunct'),
    'Detroit Falcons': _m('Detroit Falcons', 'Detroit', None, 'defunct'),
    'Indianapolis Jets': _m('Indianapolis Jets', 'Indianapolis', None, 'defunct'),
    'Indianapolis Olympians': _m('Indianapolis Olympians', 'Indianapolis', None, 'defunct'),
    'Pittsburgh Ironmen': _m('Pittsburgh Ironmen', 'Pittsburgh', None, 'defunct'),
    'Providence Steamrollers': _m('Providence Steamrollers', 'Providence', None, 'defunct'),
    'Sheboygan Red Skins': _m('Sheboygan Red Skins', 'Sheboygan', None, 'defunct'),
    'St. Louis Bombers': _m('St. Louis Bombers', 'St. Louis', None, 'defunct'),
    'Toronto Huskies': _m('Toronto Huskies', 'Toronto', None, 'defunct'),
    'Washington Capitols': _m('Washington Capitols', 'Washington', None, 'defunct'),
    'Waterloo Hawks': _m('Waterloo Hawks', 'Waterloo', None, 'defunct'),
}

def baltimore_bullets_meta(season):
    """'Baltimore Bullets' is two unrelated franchises: the original 1944-55 team
    (folded) and the 1964-73 team that descended from the Chicago Packers/Zephyrs."""
    if season <= 1955:
        return _m('Baltimore Bullets (original)', 'Baltimore', None, 'defunct')
    return _m('Washington Wizards', 'Baltimore', 'Washington Wizards')

def resolve_meta(team_name, season):
    return baltimore_bullets_meta(season) if team_name == 'Baltimore Bullets' else TEAM_META[team_name]
