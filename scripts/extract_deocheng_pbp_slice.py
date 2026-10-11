#!/usr/bin/env python3
"""Second slice of Deo_Cheng_NBA.zip: play-by-play and ESPN box scores for 2024 onward.

Why: the first slice showed deocheng's player game log is incomplete for 2024-25 and 2025-26 (many regular-season
games have players missing; the playoffs are missing or partial). The play-by-play table (sourced from
Basketball-Reference, same game ids we use) can rebuild complete box scores; 2024 is included only so the rebuild can be
checked against the other dataset on a season both cover. The ESPN box score table may hold the 2024-25 playoffs, which
neither the game log nor play-by-play has. Only the columns needed are kept (the full tables are huge).

Easiest: put this file on your Desktop, double-click it, paste the path to Deo_Cheng_NBA.zip when asked.
Or:  python extract_deocheng_pbp_slice.py "C:\\path\\Deo_Cheng_NBA.zip"
It reads an 18.6M-row table, so expect a few minutes. Writes deocheng_pbp_slice.zip next to this script.
"""
import csv
import io
import os
import sys
import traceback
import zipfile

csv.field_size_limit(2 ** 31 - 1)
MIN_SEASON = 2024

TABLES = {
    'public.play_by_play.csv': {
        'game_col': 'gameid',
        'keep': ['gameid', 'season', 'eventnum', 'period', 'clock', 'clock_seconds', 'h_pts', 'a_pts', 'team', 'playerid', 'player', 'event_type',
                 'subtype', 'result', 'dist', 'description', 'current_team', 'scorehome', 'scorevisitor', 'player1_id', 'player1_name',
                 'player1_team_abbreviation', 'player2_id', 'player2_name', 'player2_team_abbreviation', 'player3_id', 'player3_name',
                 'player3_team_abbreviation', 'source', 'br_player_id', 'action_verb']},
    'public.espn_boxscore.csv': {
        'game_col': 'br_gid',
        'keep': ['br_gid', 'nba_api_id', 'game_date', 'season', 'season_type', 'home_abbr', 'away_abbr', 'home_pts', 'away_pts', 'player_boxes']},
}


def season_ok(row, season_idx, game_idx):
    try:
        return int(float(row[season_idx])) >= MIN_SEASON
    except (ValueError, IndexError):
        gid = row[game_idx] if game_idx is not None and game_idx < len(row) else ''
        return gid[:4].isdigit() and int(gid[:4]) >= MIN_SEASON - 1


def extract(src, dest):
    with zipfile.ZipFile(src) as z, zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        names = {os.path.basename(i.filename): i for i in z.infolist() if not i.is_dir()}
        report = []
        for table, spec in TABLES.items():
            info = names.get(table)
            if info is None:
                print(f'  not found in the zip: {table}')
                report.append(f'{table}: NOT FOUND')
                continue
            print(f'reading {table} ({info.file_size / 1e6:,.0f} MB)')
            kept = total = 0
            with z.open(info) as raw, out.open(f'slice/{table}', 'w') as dst:
                text_out = io.TextIOWrapper(dst, encoding='utf-8', newline='')
                reader = csv.reader(io.TextIOWrapper(raw, encoding='utf-8', errors='replace', newline=''))
                writer = csv.writer(text_out)
                header = next(reader)
                cols = [c for c in spec['keep'] if c in header]
                idx = [header.index(c) for c in cols]
                season_idx = header.index('season')
                game_idx = header.index(spec['game_col']) if spec['game_col'] in header else None
                writer.writerow(cols)
                for row in reader:
                    total += 1
                    if season_ok(row, season_idx, game_idx):
                        writer.writerow([row[i] if i < len(row) else '' for i in idx])
                        kept += 1
                    if total % 1000000 == 0:
                        print(f'   {total:,} rows read, {kept:,} kept')
                text_out.flush()
                text_out.detach()
            missing = [c for c in spec['keep'] if c not in header]
            report.append(f'{table}: kept {kept:,} of {total:,} rows, {len(cols)} columns' + (f' (not in this file: {missing})' if missing else ''))
            print('   ' + report[-1])
        out.writestr('slice/_slice_report.txt', f'Seasons >= {MIN_SEASON}.\n' + '\n'.join(report) + '\n')


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else input('Paste the path to Deo_Cheng_NBA.zip and press Enter:\n> ')
    target = target.strip().strip('"').strip("'")
    if not os.path.isfile(target):
        print(f'\nCannot find: {target}\nTip: in File Explorer hold Shift, right-click the file, choose "Copy as path".')
        return
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deocheng_pbp_slice.zip')
    extract(target, dest)
    print(f'\nDone. Wrote {dest} ({os.path.getsize(dest) / 1e6:,.1f} MB).\nUpload that file.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        print('\nSomething went wrong. Copy the text above and send it to me.')
    if os.name == 'nt' and len(sys.argv) == 1:
        input('\nPress Enter to close...')
