import { useApi } from '../../api/hooks';
import type { Meta } from '../../api/types';

const day = (d: string) => new Date(`${d.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

/** Where this season's stats come from, when they're built from the daily box scores. */
export function LiveSeasonNote({ season, id }: { season: number; id?: string }) {
  const { data } = useApi<Meta>('/meta');
  const live = data?.live_season;
  if (!live || live.source !== 'box_scores' || live.season !== season || !live.through) return null;
  const bpm = live.estimate_accuracy?.bpm;
  return (
    <p className="section-sub" id={id} style={{ marginTop: 8, marginBottom: 0 }}>
      {season} stats are built from every box score through {day(live.through)} ({Math.round(live.games)} games). Win Shares, BPM and VORP are estimates
      {bpm ? `, fit on past seasons (tested on ${live.estimate_tested_on}: BPM within ${bpm.mae_500_min.toFixed(1)} on average)` : ''}.
    </p>
  );
}
