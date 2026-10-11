#!/usr/bin/env python3
"""Cut a small slice out of the huge Deo_Cheng_NBA.zip so it can be shared.

The full zip is dominated by an 18.6M-row play-by-play table we don't need. This
streams the zip and keeps only what the playoffs and game-log work uses:
  - player_gamelog, dim_games: 2024 onward (2024 = the 2023-24 season, which the
    other dataset also covers, so the two can be checked against each other; 2025
    and 2026 are the new seasons)
  - player_playoffs_series: 2024 onward
  - honors, awards, All-Star, EPM, salaries, game highs, team tables: whole (small)
It writes deocheng_slice.zip next to this script (expect tens of MB).

Easiest: put this file on your Desktop, double-click it, paste the path to
Deo_Cheng_NBA.zip when asked. Or:  python extract_deocheng_slice.py "C:\\path\\Deo_Cheng_NBA.zip"
"""
import csv
import io
import os
import sys
import traceback
import zipfile

csv.field_size_limit(2 ** 31 - 1)
MIN_SEASON = 2024

# table -> (column to filter on, minimum value) or None to keep every row
TABLES = {
    'public.player_gamelog.csv': ('season', MIN_SEASON),
    'public.dim_games.csv': ('season', MIN_SEASON),
    'public.player_playoffs_series.csv': ('season_end', MIN_SEASON),
    'public.player_career_honors.csv': None,
    'public.end_of_season_teams.csv': None,
    'public.player_award_shares.csv': None,
    'public.all_star_selections.csv': None,
    'public.player_epm.csv': None,
    'public.player_salaries_historical.csv': None,
    'public.player_game_highs.csv': None,
    'public.dim_franchise.csv': None,
    'public.dim_teams.csv': None,
}


def season_ok(row, col_idx, game_idx, minimum):
    try:
        return int(float(row[col_idx])) >= minimum
    except (ValueError, IndexError):
        # blank season: fall back to the year in the game id (e.g. 202501170DAL), keeping borderline rows
        gid = row[game_idx] if game_idx is not None and game_idx < len(row) else ''
        return gid[:4].isdigit() and int(gid[:4]) >= minimum - 1


def extract(src, dest):
    with zipfile.ZipFile(src) as z, zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        names = {os.path.basename(i.filename): i for i in z.infolist() if not i.is_dir()}
        report = []
        for table, rule in TABLES.items():
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
                writer.writerow(header)
                idx = header.index(rule[0]) if rule else None
                game_idx = next((header.index(c) for c in ('game_id_full', 'game_id') if c in header), None)
                for row in reader:
                    total += 1
                    if rule is None or season_ok(row, idx, game_idx, rule[1]):
                        writer.writerow(row)
                        kept += 1
                    if total % 500000 == 0:
                        print(f'   {total:,} rows read, {kept:,} kept')
                text_out.flush()                     # write everything into the zip entry before it closes
                text_out.detach()
            report.append(f'{table}: kept {kept:,} of {total:,} rows')
            print(f'   kept {kept:,} of {total:,}')
        out.writestr('slice/_slice_report.txt', f'Filtered to season >= {MIN_SEASON} where noted.\n' + '\n'.join(report) + '\n')


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else input('Paste the path to Deo_Cheng_NBA.zip and press Enter:\n> ')
    target = target.strip().strip('"').strip("'")
    if not os.path.isfile(target):
        print(f'\nCannot find: {target}\nTip: in File Explorer hold Shift, right-click the file, choose "Copy as path".')
        return
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deocheng_slice.zip')
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
