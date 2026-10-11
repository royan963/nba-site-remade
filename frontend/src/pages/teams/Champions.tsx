import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { ChampionsResponse } from '../../api/types';
import { ErrorNote, Loading, Panel, SectionHead } from '../../components/ui';
import { CoverageNote } from '../player/PlayoffPanel';
import { slugify } from './geo';

/** Every champion and runner-up. The timeline slider above highlights the chosen season. */
export function ChampionsList({ season }: { season: number }) {
  const { data, error } = useApi<ChampionsResponse>('/playoffs/champions');
  const active = useRef<HTMLTableRowElement>(null);
  useEffect(() => { active.current?.scrollIntoView({ block: 'nearest' }); }, [season, data]);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading />;
  const leaders = Object.entries(data.titles_by_franchise).slice(0, 8);
  return (
    <div id="champions-view">
      <Panel>
        <SectionHead title="Most championships" small />
        <div className="chart-controls">
          {leaders.map(([f, n]) => <Link key={f} to={`/teams/${slugify(f)}`} className="pill-btn">{f} <b>{n}</b></Link>)}
        </div>
      </Panel>
      <Panel>
        <SectionHead title="Champions by year" small>Scrub the timeline above to highlight a season.</SectionHead>
        <div className="table-scroll" style={{ maxHeight: 520 }}>
          <table className="lb-table" id="champions-table">
            <thead><tr><th>Season</th><th>Champion</th><th>Runner-up</th><th>Finals</th><th>Finals MVP</th></tr></thead>
            <tbody>
              {data.champions.map(c => (
                <tr key={c.season} ref={c.season === season ? active : undefined} className={c.season === season ? 'mvp-winner' : ''} data-season={c.season}>
                  <td>{c.season}</td>
                  <td className="name-cell"><Link to={`/teams/${slugify(c.champion_franchise)}`}>{'\u{1F3C6}'} {c.champion}</Link></td>
                  <td><Link to={`/teams/${slugify(c.runner_up_franchise)}`} className="name-link">{c.runner_up}</Link></td>
                  <td>{c.wins}&ndash;{c.losses}</td>
                  <td>{c.finals_mvp ? <Link to={`/players/${c.finals_mvp.player_id}`} className="name-link">{c.finals_mvp.player}</Link> : '\u2014'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <CoverageNote kind="teams" />
      </Panel>
    </div>
  );
}
