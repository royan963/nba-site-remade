import { useMemo } from 'react';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../../api/hooks';
import type { LeagueShooting, ShootingSeason } from '../../api/types';
import { ChartCanvas, ErrorNote, Loading, NoData, Panel, Pills, SectionHead } from '../../components/ui';
import { MONO, PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { oneOf, useQueryParam } from '../../lib/useQuery';
import { Court, ZONES, fgPctColor } from './Court';

export function ShotProfile({ playerId }: { playerId: string }) {
  const { data: seasons, error } = useApi<ShootingSeason[]>(`/players/${playerId}/shooting`);
  const { data: league } = useApi<LeagueShooting[]>('/league/shooting');
  const [seasonRaw, setSeason] = useQueryParam('shot', '');
  const [viewRaw, setView] = useQueryParam('shotView', 'court');
  const view = oneOf(viewRaw, ['court', 'bars'] as const, 'court');

  const latest = seasons?.[seasons.length - 1]?.season;
  const season = seasons?.some(s => String(s.season) === seasonRaw) ? parseInt(seasonRaw, 10) : latest;
  const row = seasons?.find(s => s.season === season);
  const leagueRow = league?.find(l => l.season === season);

  const bars = useMemo<ChartConfiguration | null>(() => {
    if (!row) return null;
    const pctOf = (v: number | null | undefined) => (v != null ? v * 100 : null);
    const datasets: ChartConfiguration['data']['datasets'] = [{
      label: 'Player FG%', data: ZONES.map(z => pctOf(row[z.pctKey] as number | null)),
      backgroundColor: ZONES.map(z => fgPctColor(row[z.pctKey] as number | null)), borderRadius: 4, order: 1,
    } as never];
    if (leagueRow) datasets.push({
      label: 'League Avg FG%', data: ZONES.map(z => pctOf(leagueRow[`avg_${z.pctKey}`])),
      backgroundColor: 'rgba(241,235,224,0.12)', borderColor: 'rgba(241,235,224,0.55)', borderWidth: 1.5, borderRadius: 4, order: 2,
    } as never);
    const shares = (i: number, ds: number) => ds === 0 ? row[ZONES[i].key] as number | null : leagueRow?.[`avg_${ZONES[i].key}`];
    return {
      type: 'bar',
      data: { labels: ZONES.map(z => z.sub), datasets },
      options: baseOptions({
        plugins: {
          legend: { display: !!leagueRow, labels: { color: PALETTE.chalkDim, font: MONO, boxWidth: 12, boxHeight: 12 } },
          tooltip: { ...TOOLTIP, callbacks: {
            label: (c: { datasetIndex: number; parsed: { y: number | null } }) =>
              `${c.datasetIndex === 0 ? 'Player' : 'League Avg'} FG%: ${c.parsed.y != null ? c.parsed.y.toFixed(2) + '%' : '\u2014'}`,
            afterLabel: (c: { datasetIndex: number; dataIndex: number }) => {
              const s = shares(c.dataIndex, c.datasetIndex);
              return `${c.datasetIndex === 0 ? 'Player' : 'League'} share of shots: ${s != null ? (s * 100).toFixed(2) + '%' : '\u2014'}`;
            },
          } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: PALETTE.chalkDim, font: { size: 10.5 } } },
          y: axis({ ticks: { callback: (v: number) => v + '%' }, title: { display: true, text: 'FG%', color: PALETTE.chalkDim, font: MONO } }),
        },
      }),
    };
  }, [row, leagueRow]);

  return (
    <Panel id="pc-shooting-panel">
      <SectionHead title="Shot Profile" small>
        {seasons && seasons.length === 0
          ? 'Shot-location tracking by NBA.com begins in the 1996/97 season \u2014 not available for this player\u2019s career.'
          : 'Shot-location tracking by NBA.com begins in the 1996/97 season. Hover or tap a zone for details.'}
      </SectionHead>
      {error && <ErrorNote error={error} />}
      {!seasons && !error && <Loading />}
      {seasons && seasons.length === 0 && <NoData>No tracked shooting-zone data for this player.</NoData>}
      {row && (
        <>
          <div className="shot-profile-controls">
            <select id="pc-shooting-season" value={season} onChange={e => setSeason(e.target.value === String(latest) ? '' : e.target.value)}>
              {seasons!.slice().reverse().map(s => <option key={s.season} value={s.season}>{s.season}</option>)}
            </select>
            <Pills options={[{ value: 'court', label: 'Court Map' }, { value: 'bars', label: 'Bar Chart' }]} value={view} onChange={v => setView(v)} />
          </div>
          {view === 'court' ? <Court data={row} /> : bars && <ChartCanvas config={bars} testId="shot-bars" />}
        </>
      )}
    </Panel>
  );
}
