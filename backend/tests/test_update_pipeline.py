"""The weekly data update rebuilds the 2025+ game files from the Deo Cheng data, which erases anything added to them.

So the eoinamoore step (2024-25 playoffs, missing 2025-26 games, 2026-27 season, play-in/Cup tags, this season's rookies)
has to run after that rebuild on every update. A manual run on 2026-10-24 showed what happens without it: the live site lost the
2024-25 playoffs again. These tests read the update script's source, since running it needs Kaggle.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = (ROOT / 'scripts' / 'update_season.py').read_text(encoding='utf8')


def at(text):
    assert text in SRC, f'update_season.py never mentions {text!r}'
    return SRC.index(text)


def test_the_update_runs_the_new_dataset_step_after_the_game_data_is_rebuilt():
    assert at("'scripts/prep_games_eoin.py'") > at("'scripts/prep_games.py'")
    assert at("'scripts/prep_games_eoin.py'") > at("'scripts/prep_playoffs.py'")
    assert at("'scripts/prep_games_eoin.py'") > at("'scripts/build_finals_mvp.py'")


def test_the_new_dataset_step_runs_before_the_models_train_and_the_page_is_built():
    assert at("'scripts/prep_games_eoin.py'") < at("'scripts/train_mvp.py'")
    assert at("'scripts/prep_games_eoin.py'") < at("'build.py'")


def test_a_failed_new_dataset_step_restores_the_previous_data():
    i = at("'scripts/prep_games_eoin.py'")
    assert 'restore(' in SRC[i:i + 400]


def test_the_update_downloads_the_three_files_the_step_needs():
    for name in ('Games.csv', 'PlayerStatistics.csv', 'Players.csv'):
        assert name in SRC
    assert 'eoinamoore/historical-nba-data-and-player-box-scores' in SRC


def test_the_raw_download_folder_is_not_committed():
    assert 'data/raw_eoin/' in (ROOT / '.gitignore').read_text(encoding='utf8')
