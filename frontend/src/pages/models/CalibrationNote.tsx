import type { LiveCalibration } from '../../api/types';

/** How sure to be this early: how often the leader at this point of past seasons, rebuilt game by game, went on to win. */
export function CalibrationNote({ id, teamGames, calibration, what }: {
  id: string; teamGames: number; calibration: LiveCalibration | null | undefined; what: 'MVP' | 'champion';
}) {
  if (!calibration || !calibration.by_games.length) return null;
  const near = calibration.by_games.reduce((a, b) => (Math.abs(b.games - teamGames) < Math.abs(a.games - teamGames) ? b : a));
  const s = calibration.seasons;
  return (
    <p className="section-sub" id={id} style={{ marginTop: 8, marginBottom: 0 }}>
      Chances are calibrated on past seasons rebuilt game by game ({s[0]}&ndash;{s[s.length - 1]}): {near.games} games in, the leader went on to
      win {Math.round(near.leader_won * 100)}% of the time and the eventual {what} was in the top 3 {Math.round(near.winner_in_top3 * 100)}% of the time.
    </p>
  );
}
