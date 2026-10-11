// Pure helpers for franchise lineages and the map (kept free of React so they
// can be unit-tested).
import { geoAlbers, geoPath, type GeoProjection } from 'd3';
import { feature } from 'topojson-client';
import type { FeatureCollection, Geometry } from 'geojson';
import type { Topology } from 'topojson-specification';
import type { TeamSeason } from '../../api/types';

export interface Franchise {
  name: string;
  slug: string;
  rows: TeamSeason[];          // sorted by season
  minSeason: number;
  maxSeason: number;
  latest: TeamSeason;
  displayName: string;
}

export const slugify = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export function buildFranchises(rows: TeamSeason[]): Map<string, Franchise> {
  const groups = new Map<string, TeamSeason[]>();
  rows.forEach(r => { if (!groups.has(r.franchise)) groups.set(r.franchise, []); groups.get(r.franchise)!.push(r); });
  const out = new Map<string, Franchise>();
  [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0])).forEach(([name, list]) => {
    list.sort((a, b) => a.season - b.season);
    const latest = list[list.length - 1];
    out.set(name, { name, slug: slugify(name), rows: list, minSeason: list[0].season, maxSeason: latest.season,
                    latest, displayName: latest.current_name || latest.team_name });
  });
  return out;
}

/** Distinct cities in order, collapsing consecutive repeats. */
export function cityPath(f: Franchise) {
  const path: { city: string; lat: number; lng: number; firstSeason: number }[] = [];
  f.rows.forEach(r => {
    if (!path.length || path[path.length - 1].city !== r.city) path.push({ city: r.city, lat: r.lat, lng: r.lng, firstSeason: r.season });
  });
  return path;
}

export function nameChain(f: Franchise) {
  const names: string[] = [];
  f.rows.forEach(r => { if (names[names.length - 1] !== r.team_name) names.push(r.team_name); });
  return names;
}

// ---- map projection --------------------------------------------------------
export const MAP_W = 760, MAP_H = 460;
const EXCLUDE = new Set(['Alaska', 'Hawaii', 'American Samoa', 'Guam', 'Commonwealth of the Northern Mariana Islands',
                         'Puerto Rico', 'United States Virgin Islands']);

export function buildBaseMap(states: Topology, canada: Topology) {
  const statesGeo = feature(states, states.objects.states) as unknown as FeatureCollection<Geometry, { name: string }>;
  const mainland: FeatureCollection = { type: 'FeatureCollection', features: statesGeo.features.filter(f => !EXCLUDE.has(f.properties.name)) };
  const canadaGeo = feature(canada, canada.objects.canada) as unknown as GeoJSON.Feature;
  // Fit to the continental US with headroom above for Canada (fitting Canada's
  // full Arctic extent would shrink the US badly).
  const projection = geoAlbers().fitExtent([[20, 120], [MAP_W - 20, MAP_H - 20]], mainland);
  const path = geoPath(projection);
  return {
    projection,
    canadaPath: path(canadaGeo) || '',
    statePaths: mainland.features.map(f => path(f) || ''),
  };
}

// ---- markers ------------------------------------------------------------------
export interface Marker { franchise: Franchise; row: TeamSeason; active: boolean; trueX: number; trueY: number; x: number; y: number; offset: boolean }

/** Markers for one season: active teams plus a one-season "ghost" for teams that just moved or folded. */
export function markersForSeason(franchises: Iterable<Franchise>, season: number, projection: GeoProjection): Marker[] {
  const out: Marker[] = [];
  for (const f of franchises) {
    const upTo = f.rows.filter(r => r.season <= season);
    if (!upTo.length) continue;
    const row = upTo[upTo.length - 1];
    const active = row.season === season;
    if (!active && season - row.season > 1 && season > f.maxSeason) continue;
    const p = projection([row.lng, row.lat]) || [-1000, -1000];
    out.push({ franchise: f, row, active, trueX: p[0], trueY: p[1], x: p[0], y: p[1], offset: false });
  }
  return layoutMarkers(out);
}

/**
 * Keep badges from overlapping: teams in the same city (Lakers/Clippers) are
 * fanned into a ring, then any badges still closer than MIN_SEP are nudged
 * apart a little at a time.
 */
export function layoutMarkers<T extends { trueX: number; trueY: number; x: number; y: number; offset: boolean }>(markers: T[]): T[] {
  const SAME = 6, FAN = 24, MIN_SEP = 38, PASSES = 40, STEP = 0.5;
  const buckets = new Map<string, T[]>();
  markers.forEach(m => {
    const key = `${Math.round(m.trueX / SAME)}:${Math.round(m.trueY / SAME)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(m);
  });
  buckets.forEach(group => {
    if (group.length === 1) { group[0].x = group[0].trueX; group[0].y = group[0].trueY; return; }
    const cx = group.reduce((s, m) => s + m.trueX, 0) / group.length;
    const cy = group.reduce((s, m) => s + m.trueY, 0) / group.length;
    const r = group.length <= 2 ? FAN : FAN * (1 + (group.length - 2) * 0.35);
    group.forEach((m, k) => {
      const a = -Math.PI / 2 + (k * 2 * Math.PI) / group.length;
      m.x = cx + r * Math.cos(a);
      m.y = cy + r * Math.sin(a);
    });
  });
  for (let pass = 0; pass < PASSES; pass++) {
    let moved = false;
    for (let i = 0; i < markers.length; i++) {
      for (let j = i + 1; j < markers.length; j++) {
        const a = markers[i], b = markers[j];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d = Math.hypot(dx, dy);
        if (d < 0.01) { dx = 0.5; dy = 0.5; d = 0.01; }            // deterministic nudge for exact overlaps
        if (d < MIN_SEP) {
          moved = true;
          const push = (MIN_SEP - d) * STEP, ux = dx / d, uy = dy / d;
          a.x -= (ux * push) / 2; a.y -= (uy * push) / 2;
          b.x += (ux * push) / 2; b.y += (uy * push) / 2;
        }
      }
    }
    if (!moved) break;
  }
  markers.forEach(m => { m.offset = Math.abs(m.x - m.trueX) > 1 || Math.abs(m.y - m.trueY) > 1; });
  return markers;
}
