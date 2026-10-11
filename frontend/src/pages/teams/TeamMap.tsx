import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Topology } from 'topojson-specification';
import { Loading } from '../../components/ui';
import { MAP_H, MAP_W, buildBaseMap, cityPath, markersForSeason, type Franchise } from './geo';

type BaseMap = ReturnType<typeof buildBaseMap>;

/** US + Canada map with one badge per franchise for the chosen season. */
export function TeamMap({ franchises, season }: { franchises: Map<string, Franchise>; season: number }) {
  const navigate = useNavigate();
  const [base, setBase] = useState<BaseMap | null>(null);
  const [hover, setHover] = useState<{ text: string; meta: string; inactive: boolean; x: number; y: number } | null>(null);

  useEffect(() => {      // map outlines are a separate chunk, loaded with this view
    let live = true;
    Promise.all([import('../../data/states-10m.json'), import('../../data/canada_topo.json')]).then(([s, c]) => {
      if (live) setBase(buildBaseMap(s.default as unknown as Topology, c.default as unknown as Topology));
    });
    return () => { live = false; };
  }, []);

  const markers = useMemo(() => {
    if (!base) return [];
    const list = markersForSeason(franchises.values(), season, base.projection);
    return list.sort((a, b) => Number(a.active) - Number(b.active));   // active badges on top
  }, [base, franchises, season]);

  const relocations = useMemo(() => {
    if (!base) return [];
    const lines: string[] = [];
    franchises.forEach(f => {
      const stops = cityPath(f).filter(p => p.firstSeason <= season);
      for (let i = 0; i < stops.length - 1; i++) {
        const p1 = base.projection([stops[i].lng, stops[i].lat]), p2 = base.projection([stops[i + 1].lng, stops[i + 1].lat]);
        if (!p1 || !p2) continue;
        const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2 - 18;
        lines.push(`M${p1[0]},${p1[1]} Q${mx},${my} ${p2[0]},${p2[1]}`);
      }
    });
    return lines;
  }, [base, franchises, season]);

  if (!base) return <Loading text={'Loading map\u2026'} />;
  return (
    <div id="us-map-container" style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${MAP_W} ${MAP_H}`} preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Map of the United States and Canada showing NBA team locations by season">
        <path className="state-path country-path" d={base.canadaPath} />
        <g>{base.statePaths.map((d, i) => <path key={i} className="state-path" d={d} />)}</g>
        <g>{relocations.map((d, i) => <path key={i} className="relocation-path" d={d} />)}</g>
        <g>{markers.filter(m => m.offset).map(m => (
          <line key={m.franchise.name} className="marker-leader" x1={m.trueX} y1={m.trueY} x2={m.x} y2={m.y} />
        ))}</g>
        <g>
          {markers.map(m => {
            const r = m.active ? 14 : 8;
            return (
              <g key={m.franchise.name} className="team-marker" transform={`translate(${m.x},${m.y})`}
                 style={{ opacity: m.active ? 1 : 0.45, cursor: 'pointer' }}
                 onClick={() => navigate(`/teams/${m.franchise.slug}`)}
                 onMouseMove={e => {
                   const box = e.currentTarget.ownerSVGElement!.parentElement!.getBoundingClientRect();
                   setHover({ text: m.row.team_name, meta: `${m.row.city} \u00b7 ${m.row.season}${m.row.w != null ? ` \u00b7 ${m.row.w}-${m.row.l}` : ''}`,
                              inactive: !m.active, x: e.clientX - box.left + 14, y: e.clientY - box.top - 10 });
                 }}
                 onMouseLeave={() => setHover(null)}>
                <circle className="marker-badge-ring" r={r + 1.5} fill="none" stroke={m.row.secondary_color} strokeWidth={m.active ? 1.5 : 1} />
                <circle className="marker-badge-fill" r={r} fill={m.row.primary_color} />
                <text className="marker-badge-text" fontSize={m.active ? 9.5 : 7.5} fontWeight={700} fontFamily="'JetBrains Mono', monospace"
                      fill={m.row.secondary_color} textAnchor="middle" dominantBaseline="central">{m.row.abbr || m.row.badge_code}</text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="map-tooltip" style={{ opacity: hover ? 1 : 0, left: hover?.x, top: hover?.y }}>
        {hover && <>
          <div className="mt-name">{hover.text}</div>
          <div className="mt-meta">{hover.meta}</div>
          {hover.inactive && <div className="mt-meta" style={{ marginTop: 3, opacity: 0.7 }}>Not active this season</div>}
        </>}
      </div>
    </div>
  );
}
