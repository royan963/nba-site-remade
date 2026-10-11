import { useMemo } from 'react';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../api/hooks';
import type { LeagueTrend } from '../api/types';
import { ChartCanvas, ErrorNote, Loading, Panel, Pills, SectionHead } from '../components/ui';
import { PALETTE, TOOLTIP, axis, baseOptions } from '../lib/chart';
import { fmtNum, fmtPct } from '../lib/format';
import { oneOf, useQueryParam } from '../lib/useQuery';

const STATS = [
  { value: 'pace', label: 'Pace', pct: false },
  { value: 'pts_per_game', label: 'Points/Game', pct: false },
  { value: 'o_rtg', label: 'Off. Rating', pct: false },
  { value: 'x3p_ar', label: '3PA Rate', pct: true },
  { value: 'x3p_percent', label: '3P%', pct: true },
  { value: 'fg_percent', label: 'FG%', pct: true },
  { value: 'ast_per_game', label: 'Assists/Game', pct: false },
  { value: 'orb_per_game', label: 'Off. Rebounds/Game', pct: false },
  { value: 'ts_percent', label: 'True Shooting %', pct: true },
] as const;
type StatKey = typeof STATS[number]['value'];

export default function Evolution() {
  const { data: era, error } = useApi<LeagueTrend[]>('/league/trends');
  const [raw, setStat] = useQueryParam('stat', 'pace');
  const stat = oneOf<StatKey>(raw, STATS.map(s => s.value), 'pace');
  const def = STATS.find(s => s.value === stat)!;
  const fmt = (v: number) => (def.pct ? fmtPct(v) : fmtNum(v));

  const main = useMemo<ChartConfiguration | null>(() => !era ? null : ({
    type: 'line',
    data: { labels: era.map(e => e.season), datasets: [{
      label: def.label, data: era.map(e => e[stat] as number | null), borderColor: PALETTE.amber, backgroundColor: PALETTE.amberDim,
      tension: 0.25, pointRadius: 0, pointHoverRadius: 5, borderWidth: 2.5, fill: true }] },
    options: baseOptions({
      plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: { label: (c: { parsed: { y: number } }) => fmt(c.parsed.y) } } },
      scales: { x: axis({ ticks: { maxTicksLimit: 14 } }), y: axis({ ticks: { callback: (v: number) => fmt(v) } }) },
    }),
  }), [era, stat]);   // eslint-disable-line react-hooks/exhaustive-deps

  const threes = useMemo<ChartConfiguration | null>(() => !era ? null : ({
    type: 'line',
    data: { labels: era.map(e => e.season), datasets: [{ label: '3PA Rate', data: era.map(e => e.x3p_ar), borderColor: PALETTE.wood,
      backgroundColor: 'rgba(217,154,92,0.12)', tension: 0.25, pointRadius: 0, borderWidth: 2, fill: true }] },
    options: baseOptions({
      plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: { label: (c: { parsed: { y: number } }) => fmtPct(c.parsed.y) } } },
      scales: { x: axis({ ticks: { maxTicksLimit: 8 } }), y: axis({ ticks: { callback: (v: number) => fmtPct(v, 0) } }) },
    }),
  }), [era]);

  const ratings = useMemo<ChartConfiguration | null>(() => !era ? null : ({
    type: 'line',
    data: { labels: era.map(e => e.season), datasets: [
      { label: 'Off. Rating', data: era.map(e => e.o_rtg), borderColor: PALETTE.amber, tension: 0.25, pointRadius: 0, borderWidth: 2 },
      { label: 'Def. Rating', data: era.map(e => e.d_rtg), borderColor: PALETTE.blue, tension: 0.25, pointRadius: 0, borderWidth: 2 }] },
    options: baseOptions({ scales: { x: axis({ ticks: { maxTicksLimit: 8 } }), y: axis() } }),
  }), [era]);

  return (
    <section className="view active" id="view-evolution">
      <SectionHead title="Era Evolution">Pick a stat and watch eight decades unfold. Hover any point for the season's league average.</SectionHead>
      {error && <ErrorNote error={error} />}
      {!era && !error && <Loading />}
      {main && threes && ratings && (
        <>
          <Panel>
            <Pills options={STATS.map(s => ({ value: s.value, label: s.label }))} value={stat} onChange={v => setStat(v)} id="evo-stat-pills" />
            <ChartCanvas config={main} tall />
          </Panel>
          <div className="panel-row">
            <Panel>
              <SectionHead title="The 3-Point Revolution" small>Share of all field-goal attempts that are three-pointers.</SectionHead>
              <ChartCanvas config={threes} />
            </Panel>
            <Panel>
              <SectionHead title="Offense vs. Defense Rating" small>Points produced / allowed per 100 possessions.</SectionHead>
              <ChartCanvas config={ratings} />
            </Panel>
          </div>
        </>
      )}
    </section>
  );
}
