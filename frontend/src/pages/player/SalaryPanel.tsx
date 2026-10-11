import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import type { ChartConfiguration } from 'chart.js';
import { useApi } from '../../api/hooks';
import type { Contract, PlayerSalaries } from '../../api/types';
import { ChartCanvas, ErrorNote, Loading, Panel, SectionHead } from '../../components/ui';
import { PALETTE, TOOLTIP, axis, baseOptions } from '../../lib/chart';
import { DASH, fmtMoney } from '../../lib/format';
import { slugify } from '../teams/geo';

/** 2026 -> "2025-26" */
export const seasonLabel = (s: number) => `${s - 1}-${String(s).slice(2)}`;
const OPTION = { player_option: 'Player option', team_option: 'Team option' } as const;

export function ContractNote({ asOf }: { asOf: string | null }) {
  if (!asOf) return null;
  const date = new Date(`${asOf}T12:00:00Z`).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  return <p className="section-sub" style={{ margin: '8px 0 0' }}>Contracts as of {date} (Basketball-Reference); deals signed after that aren&rsquo;t shown yet. Salaries before then are what each team paid, from 1996-97 on.</p>;
}

export function OptionChip({ option }: { option: keyof typeof OPTION | null }) {
  return option ? <span className={`result-chip ${option === 'player_option' ? 'finalist' : ''}`} title={OPTION[option]}>{option === 'player_option' ? 'PO' : 'TO'}</span> : null;
}

/** A player's pay by season (blue: paid; amber: still under contract), the seasons table and his current contract. */
export function SalaryPanel({ playerId }: { playerId: string }) {
  const { data, error } = useApi<PlayerSalaries>(`/players/${playerId}/salaries`);
  const current = data?.contract.season ?? null;
  const future = useMemo(() => {
    const by: Record<number, number> = {};
    for (const c of data?.contract.teams ?? []) for (const s of c.seasons) if (current && s.season > current) by[s.season] = (by[s.season] ?? 0) + s.salary;
    return Object.entries(by).map(([s, v]) => ({ season: Number(s), total: v }));
  }, [data, current]);

  const config = useMemo<ChartConfiguration | null>(() => {
    if (!data || !data.seasons.length) return null;
    const bars = [...data.seasons.map(s => ({ season: s.season, total: s.total, future: false })), ...future.map(f => ({ ...f, future: true }))];
    return {
      type: 'bar',
      data: { labels: bars.map(b => seasonLabel(b.season)), datasets: [{
        label: 'Salary', data: bars.map(b => b.total / 1e6),
        backgroundColor: bars.map(b => (b.future ? PALETTE.amberDim : PALETTE.blueDim)),
        borderColor: bars.map(b => (b.future ? PALETTE.amber : PALETTE.blue)), borderWidth: 1.5,
      }] },
      options: baseOptions({
        plugins: { legend: { display: false }, tooltip: { ...TOOLTIP, callbacks: {
          label: (i: { dataIndex: number }) => `${fmtMoney(bars[i.dataIndex].total)}${bars[i.dataIndex].future ? ' (under contract)' : ''}`,
        } } },
        scales: { x: axis({ ticks: { maxTicksLimit: 12 } }), y: axis({ ticks: { callback: (v: number) => `$${v}M` } }) },
      }),
    } as ChartConfiguration;
  }, [data, future]);

  if (error) return <Panel id="pc-salary-panel"><ErrorNote error={error} /></Panel>;
  if (!data) return <Panel id="pc-salary-panel"><Loading /></Panel>;
  if (!data.seasons.length && !data.contract.teams.length) return null;
  const last = data.seasons[data.seasons.length - 1];
  const remaining = future.reduce((a, f) => a + f.total, 0);
  return (
    <Panel id="pc-salary-panel">
      <SectionHead title="Salary & contract" small>
        What he was paid each season{data.first_season && data.first_season > 1997 ? '' : ' (records start in 1996-97)'}, and what his current contract pays from here.
      </SectionHead>
      <div className="player-stat-row" id="pc-salary-stats">
        {[['Career earnings', fmtMoney(data.career_earnings), data.seasons.length ? `${data.seasons.length} seasons` : ''],
          ...(last ? [[`${seasonLabel(last.season)} salary`, fmtMoney(last.total), `#${last.rank} of ${last.players} in the league`]] : []),
          ...(remaining ? [['Still owed after this season', fmtMoney(remaining), `through ${seasonLabel(future[future.length - 1].season)}`]] : [])].map(([l, v, sub]) => (
          <div className="ps-cell" key={l}><div className="v">{v}</div><div className="l">{l}{sub && ` · ${sub}`}</div></div>
        ))}
      </div>
      {config && <ChartCanvas config={config} testId="salary-chart" />}
      {data.contract.teams.length > 0 && <ContractTable contracts={data.contract.teams} current={current} />}
      {data.seasons.length > 0 && (
        <details className="lineup-notes" style={{ marginTop: 12 }}>
          <summary>Salary by season</summary>
          <div className="table-scroll">
            <table className="lb-table" id="pc-salary-table">
              <thead><tr><th>Season</th><th>Team</th><th>Salary</th><th>League rank</th></tr></thead>
              <tbody>
                {[...data.seasons].reverse().map(s => (
                  <tr key={s.season}>
                    <td>{seasonLabel(s.season)}</td>
                    <td>{s.teams.map((t, i) => <span key={t.team}>{i > 0 && ', '}{t.franchise ? <Link to={`/teams/${slugify(t.franchise)}`} className="name-link">{t.team_name ?? t.team}</Link> : t.team}{s.teams.length > 1 && ` ${fmtMoney(t.salary)}`}</span>)}</td>
                    <td>{fmtMoney(s.total)}</td>
                    <td>#{s.rank} <span className="similar-meta">of {s.players}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      <ContractNote asOf={data.contract.as_of} />
    </Panel>
  );
}

function ContractTable({ contracts, current }: { contracts: Contract[]; current: number | null }) {
  const seasons = [...new Set(contracts.flatMap(c => c.seasons.map(s => s.season)))].sort();
  return (
    <div className="table-scroll" style={{ marginTop: 12 }}>
      <table className="lb-table" id="pc-contract-table">
        <thead><tr><th>Contract</th>{seasons.map(s => <th key={s}>{seasonLabel(s)}</th>)}<th>Guaranteed</th></tr></thead>
        <tbody>
          {contracts.map(c => (
            <tr key={c.team}>
              <td className="name-cell">{c.team}{c.two_way && <span className="similar-meta"> two-way</span>}
                {c.notes.length > 0 && <div className="mvp-flag">{c.notes.join(' ')}</div>}</td>
              {seasons.map(s => {
                const x = c.seasons.find(y => y.season === s);
                return <td key={s} className={s === current ? 'sorted' : ''}>{x ? <>{fmtMoney(x.salary)} <OptionChip option={x.option} /></> : DASH}</td>;
              })}
              <td>{fmtMoney(c.guaranteed)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
