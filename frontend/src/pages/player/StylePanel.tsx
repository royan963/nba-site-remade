import { Link } from 'react-router-dom';
import { useApi } from '../../api/hooks';
import type { PlayerArchetypes, StyleShare } from '../../api/types';
import { Panel, SectionHead } from '../../components/ui';
import { roleColor } from '../models/archetypeColors';

/** A stacked bar of style shares (career or one season). */
export function StyleBar({ mix, thin }: { mix: StyleShare[]; thin?: boolean }) {
  const total = mix.reduce((a, m) => a + m.share, 0) || 1;
  return (
    <div className={`style-bar ${thin ? 'thin' : ''}`} aria-label={mix.map(m => `${m.name} ${m.share}%`).join(', ')}>
      {mix.map(m => <span key={m.key} style={{ width: `${(m.share / total) * 100}%`, background: roleColor(m.key) }} title={`${m.name} ${m.share}%`} />)}
    </div>
  );
}

/** The player's mix of playing styles over his career and each season (from the archetype model). */
export function StylePanel({ playerId }: { playerId: string }) {
  const { data } = useApi<PlayerArchetypes>(`/players/${playerId}/archetypes`);
  if (!data || !data.main || !data.mix.length) return null;
  const shown = data.mix.filter(m => m.share >= 5);
  return (
    <Panel id="pc-style-panel">
      <SectionHead title="Playing style" small>
        Most players blend roles. This is how his minutes split across playing styles over his career (seasons with 1,000+ minutes), and season by season. Mostly a{' '}
        <Link to={`/models/archetypes?role=${data.main.key}`}><b style={{ color: roleColor(data.main.key) }}>{data.main.name}</b></Link>:{' '}
        {data.main.description.charAt(0).toLowerCase() + data.main.description.slice(1)}
      </SectionHead>
      <StyleBar mix={data.mix} />
      <div className="style-legend" id="pc-style-mix">
        {shown.map(m => (
          <Link key={m.key} to={`/models/archetypes?role=${m.key}`} className="style-legend-item">
            <span className="archetype-dot" style={{ background: roleColor(m.key) }} />{m.name} <b>{m.share}%</b>
          </Link>
        ))}
      </div>
      <div className="style-strip" id="pc-style-strip">
        {data.seasons.map(s => (
          <Link key={s.season} to={`/models/archetypes?role=${s.key}`} className="style-chip" style={{ borderColor: roleColor(s.key) }}
                title={`${s.season}: ${s.mix.map(m => `${m.name} ${m.share}%`).join(', ')}${s.features_used < data.features_total ? ' \u00b7 based on fewer stats (older season)' : ''}`}>
            <span className="style-chip-season">{s.season}</span>
            <span className="style-chip-role" style={{ color: roleColor(s.key) }}>{s.name}</span>
            {s.mix.length > 0 && <StyleBar mix={s.mix} thin />}
          </Link>
        ))}
      </div>
    </Panel>
  );
}
