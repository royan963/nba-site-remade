import { useEffect, useMemo, useRef, useState } from 'react';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../api/hooks';
import type { LeaderRow, LeagueTrend } from '../api/types';
import { ChartCanvas, ErrorNote, Loading, Panel, PlayButton, SeasonSlider, SectionHead, usePlayback } from '../components/ui';
import { MONO, PALETTE, axis, baseOptions } from '../lib/chart';
import { fmtInt, fmtNum, fmtPct } from '../lib/format';

function eraLabel(season: number) {
  if (season < 1950) return 'BAA Founding Era';
  if (season < 1954) return 'Pre-Shot-Clock Era';
  if (season < 1968) return 'Russell Dynasty Era';
  if (season < 1980) return 'Run-and-Gun Era';
  if (season < 1992) return 'Early 3PT / Showtime Era';
  if (season < 2005) return 'Hand-Check Era';
  if (season < 2015) return 'Pace-and-Space Dawn';
  return 'Three-Point Era';
}

const SB_STATS: { key: keyof LeagueTrend; label: string; unit?: string; pct?: boolean }[] = [
  { key: 'pace', label: 'Pace', unit: 'poss/48' },
  { key: 'pts_per_game', label: 'Pts / Game', unit: 'pts' },
  { key: 'x3p_ar', label: '3PA Rate', pct: true },
  { key: 'x3p_percent', label: '3P%', pct: true },
  { key: 'o_rtg', label: 'Off. Rating' },
  { key: 'ts_percent', label: 'True Shooting', pct: true },
];

export default function Overview() {
  const { data: era, error } = useApi<LeagueTrend[]>('/league/trends');
  const { data: top } = useApi<LeaderRow[]>('/leaders?stat=pts&limit=1');
  if (error) return <section className="view active"><ErrorNote error={error} /></section>;
  if (!era) return <section className="view active"><Loading /></section>;
  return <OverviewContent era={era} topScorer={top?.[0]} />;
}

function OverviewContent({ era, topScorer }: { era: LeagueTrend[]; topScorer?: LeaderRow }) {
  const first = era[0].season, latest = era[era.length - 1].season;
  const [season, setSeason] = useState(latest);
  const prevRef = useRef<LeagueTrend | null>(null);
  const { playing, toggle } = usePlayback(first, latest, season, setSeason);
  const bySeason = useMemo(() => new Map(era.map(e => [e.season, e])), [era]);
  const row = bySeason.get(season)!;

  // Deltas vs the previous season are shown while the timeline plays.
  const last = prevRef.current;
  const showDelta = playing && last?.season === season - 1;
  useEffect(() => { prevRef.current = row; });

  const ticker = useMemo(() => {
    const withPace = era.filter(e => e.pace != null);
    const peak = withPace.reduce((a, b) => (b.pace! > a.pace! ? b : a));
    const low = withPace.reduce((a, b) => (b.pace! < a.pace! ? b : a));
    const top3 = era.reduce((a, b) => ((b.x3p_ar || 0) > (a.x3p_ar || 0) ? b : a));
    return [
      { label: 'Fastest season', value: fmtNum(peak.pace), sub: `pace \u00b7 ${peak.season}` },
      { label: 'Slowest season', value: fmtNum(low.pace), sub: `pace \u00b7 ${low.season}` },
      { label: 'Peak 3PT rate', value: fmtPct(top3.x3p_ar), sub: `of all shots \u00b7 ${top3.season}` },
      { label: 'All-time scorer', value: topScorer?.player ?? '\u2026', sub: topScorer ? `${fmtInt(topScorer.pts)} pts` : '' },
      { label: 'Seasons tracked', value: String(era.length), sub: `${first}\u2013${latest}` },
    ];
  }, [era, topScorer, first, latest]);

  const chart = useMemo<ChartConfiguration>(() => ({
    type: 'line',
    data: {
      labels: era.map(e => e.season),
      datasets: [
        { label: 'Pace (poss/48)', data: era.map(e => e.pace), borderColor: PALETTE.blue, backgroundColor: PALETTE.blueDim,
          yAxisID: 'y', tension: 0.25, pointRadius: 0, borderWidth: 2, fill: true },
        { label: 'Points / Game', data: era.map(e => e.pts_per_game), borderColor: PALETTE.amber, backgroundColor: PALETTE.amberDim,
          yAxisID: 'y1', tension: 0.25, pointRadius: 0, borderWidth: 2, fill: true },
      ],
    },
    options: baseOptions({
      scales: {
        x: axis({ ticks: { maxTicksLimit: 12 } }),
        y: axis({ position: 'left', title: { display: true, text: 'Pace', color: PALETTE.blue, font: MONO } }),
        y1: { position: 'right', grid: { display: false }, ticks: { color: PALETTE.chalkDim },
              title: { display: true, text: 'Pts/Game', color: PALETTE.amber, font: MONO } },
      },
    }),
  }), [era]);

  return (
    <section className="view active" id="view-overview">
      <div className="hero">
        <h1 className="hero-headline">Basketball didn't evolve gradually.<br />It <span className="accent">cratered</span>, then <span className="accent2">exploded</span>.</h1>
        <p className="hero-sub">Eighty seasons of NBA box scores, distilled. Pace bottomed out in the mid-2000s after the run-and-gun 1960s. Then the three-point shot rewired the sport from the perimeter in. Scrub the timeline below to feel the league change era by era — then dig into leaderboards, player careers, and team-by-team history.</p>
        <div className="ticker" id="hero-ticker">
          {ticker.map(c => (
            <div className="ticker-cell" key={c.label}>
              <span className="t-label">{c.label}</span>
              <div className="t-value">{c.value}</div>
              <div className="t-sub">{c.sub}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="scoreboard">
        <div className="scoreboard-top">
          <div className="scoreboard-season">
            <span id="sb-season">{season}</span>
            <span className="era-label">{eraLabel(season)}</span>
          </div>
          <div className="playback-row" style={{ marginTop: 0 }}>
            <PlayButton playing={playing} onClick={toggle} />
            <span className="playback-label">{playing ? 'Playing through history\u2026' : 'Drag the slider \u2014 or hit play to watch the league evolve'}</span>
          </div>
        </div>
        <div className="scoreboard-stats">
          {SB_STATS.map(s => {
            const v = row[s.key] as number | null;
            const pv = last?.[s.key] as number | null | undefined;
            let delta = null;
            if (showDelta && v != null && pv != null && pv !== 0) {
              const diff = v - pv;
              const dir = Math.abs(diff) < Math.abs(pv) * 0.001 ? 'flat' : diff > 0 ? 'up' : 'down';
              delta = <span className={`delta ${dir}`}>{dir === 'up' ? '\u25B2' : dir === 'down' ? '\u25BC' : '\u00b7'} {diff > 0 ? '+' : ''}{fmtNum(diff, 2)}</span>;
            }
            return (
              <div className="sb-stat" key={s.key as string}>
                <span className="label">{s.label}</span>
                <div className="value">{s.pct ? fmtPct(v) : fmtNum(v)}<span className="unit">{s.unit}</span></div>
                {delta}
              </div>
            );
          })}
        </div>
        <SeasonSlider min={first} max={latest} value={season} onChange={setSeason} ticks={[first, 1960, 1980, 2000, latest]} id="season-slider" />
      </div>

      <Panel>
        <SectionHead title="League pace & scoring, side by side">
          Pace (possessions per 48 minutes) and points per game don't move together. The 60s were fast AND high-scoring. Today's game is slower than the 60s, but scores just as much — because of where the points come from.
        </SectionHead>
        <ChartCanvas config={chart} tall />
      </Panel>
    </section>
  );
}
