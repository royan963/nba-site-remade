import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { enc } from '../../api/client';
import { useApi } from '../../api/hooks';
import type { TeamSalaries as TeamSalariesData } from '../../api/types';
import { ChartCanvas, ErrorNote, Loading, SectionHead } from '../../components/ui';
import { PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { DASH, fmtMoney } from '../../lib/format';
import { ContractNote, OptionChip, seasonLabel } from '../player/SalaryPanel';
import type { Franchise } from './geo';

const LINES = [['salary_cap', 'Salary cap'], ['luxury_tax', 'Luxury tax'], ['first_apron', 'First apron'], ['second_apron', 'Second apron']] as const;

/** Payroll by season (paid, then committed under current contracts) and the current salary sheet. */
export function TeamSalaries({ franchise }: { franchise: Franchise }) {
  const { data, error } = useApi<TeamSalariesData>(`/teams/${enc(franchise.name)}/salaries`);
  const config = useMemo<ChartConfiguration | null>(() => {
    if (!data || !data.payroll.length) return null;
    const p = data.payroll;
    return {
      type: 'bar',
      data: { labels: p.map(x => seasonLabel(x.season)), datasets: [
        { type: 'bar', label: 'Payroll', data: p.map(x => x.total / 1e6),
          backgroundColor: p.map(x => (x.kind === 'committed' ? PALETTE.amberDim : PALETTE.blueDim)),
          borderColor: p.map(x => (x.kind === 'committed' ? PALETTE.amber : PALETTE.blue)), borderWidth: 1.5 },
        { type: 'line', label: 'League average', data: p.map(x => (x.league_avg == null ? null : x.league_avg / 1e6)),
          borderColor: PALETTE.chalkDim, borderDash: [4, 4], pointRadius: 0, borderWidth: 1.5, spanGaps: false },
      ] },
      options: baseOptions({
        plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: {
          label: (i: { dataIndex: number; datasetIndex: number }) => {
            const x = p[i.dataIndex];
            return i.datasetIndex === 0
              ? `${fmtMoney(x.total)} · ${x.players} players${x.kind === 'committed' ? ' under contract so far' : ''}`
              : `League average ${fmtMoney(x.league_avg)}`;
          },
        } } },
        scales: { x: axis({ ticks: { maxTicksLimit: 14 } }), y: axis({ ticks: { callback: (v: number) => `$${v}M` } }) },
      }),
    } as ChartConfiguration;
  }, [data]);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  if (!data.payroll.length) return null;
  const current = data.season;
  const now = data.payroll.find(p => p.season === current);
  const seasons = [...new Set(data.sheet.flatMap(c => c.seasons.map(s => s.season)))].sort();
  return (
    <div className="roster-section" id="team-salaries">
      <SectionHead title="Payroll" small>
        What the team paid its players each season since 1996-97, then what it has committed under current contracts (amber). Dashed line: league average.
      </SectionHead>
      {now && data.rules && (
        <div className="player-stat-row" id="team-payroll-stats">
          <div className="ps-cell"><div className="v">{fmtMoney(now.total)}</div><div className="l">{seasonLabel(now.season)} payroll &middot; {now.players} players</div></div>
          {LINES.filter(([k]) => data.rules![k]).map(([k, label]) => {
            const diff = now.total - data.rules![k]!;
            return <div className="ps-cell" key={k}><div className="v">{fmtMoney(Math.abs(diff))}</div>
              <div className="l">{diff >= 0 ? 'over' : 'under'} the {label.toLowerCase()} ({fmtMoney(data.rules![k])})</div></div>;
          })}
        </div>
      )}
      {config && <ChartCanvas config={config} testId="payroll-chart" />}
      {data.sheet.length > 0 && (
        <div className="table-scroll" style={{ marginTop: 12 }}>
          <table className="lb-table" id="team-contracts-table">
            <thead><tr><th>Player</th>{seasons.map(s => <th key={s}>{seasonLabel(s)}</th>)}<th>Guaranteed</th></tr></thead>
            <tbody>
              {data.sheet.map(c => (
                <tr key={c.player_id}>
                  <td className="name-cell">
                    <Link to={`/players/${c.player_id}`}>{c.player ?? c.player_id}</Link>
                    {c.two_way && <span className="similar-meta"> two-way</span>}
                    {c.notes.some(n => /waived|ended|released/i.test(n)) && <span className="similar-meta" title={c.notes.join(' ')}> no longer on roster</span>}
                  </td>
                  {seasons.map(s => {
                    const x = c.seasons.find(y => y.season === s);
                    return <td key={s}>{x ? <>{fmtMoney(x.salary)} <OptionChip option={x.option} /></> : DASH}</td>;
                  })}
                  <td>{fmtMoney(c.guaranteed)}</td>
                </tr>
              ))}
              <tr className="career-row">
                <td><b>Total</b></td>
                {seasons.map(s => <td key={s}>{fmtMoney(data.sheet.reduce((a, c) => a + (c.seasons.find(y => y.season === s)?.salary ?? 0), 0))}</td>)}
                <td>{fmtMoney(data.sheet.reduce((a, c) => a + (c.guaranteed ?? 0), 0))}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
      <p className="section-sub" style={{ margin: '8px 0 0' }}>PO / TO: player or team option. Before {current ? seasonLabel(current) : 'this season'}, payrolls add up the player salaries on record, which can miss a few end-of-bench or waived players.</p>
      <ContractNote asOf={data.as_of} />
    </div>
  );
}
