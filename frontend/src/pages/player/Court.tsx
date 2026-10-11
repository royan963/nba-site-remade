// Half-court shot chart. Geometry uses NBA regulation dimensions (feet),
// scaled to SVG units with the basket as the origin.
import { useState } from 'react';
import type { ShootingSeason } from '../../api/types';
import { fmtPct } from '../../lib/format';

const SCALE = 10;
const W = 50 * SCALE;
const H = 42 * SCALE;
const BX = W / 2;
const BY = 5.25 * SCALE;
const pt = (xFt: number, yFt: number): [number, number] => [BX + xFt * SCALE, BY + yFt * SCALE];

export const ZONES = [
  { key: 'pct_fga_0_3', pctKey: 'fg_pct_0_3', label: 'Restricted Area', sub: '0-3 ft', rInner: 0, rOuter: 4 },
  { key: 'pct_fga_3_10', pctKey: 'fg_pct_3_10', label: 'Short Range', sub: '3-10 ft', rInner: 4, rOuter: 10 },
  { key: 'pct_fga_10_16', pctKey: 'fg_pct_10_16', label: 'Mid-Range', sub: '10-16 ft', rInner: 10, rOuter: 16 },
  { key: 'pct_fga_16_3p', pctKey: 'fg_pct_16_3p', label: 'Long Mid-Range', sub: '16 ft-3PT', rInner: 16, rOuter: 23 },
  { key: 'pct_fga_3p', pctKey: 'fg_pct_3p', label: 'Three-Point', sub: 'Beyond the arc', rInner: 23, rOuter: 31 },
] as const;

/** Neutral analytic heat scale for FG%: cool blue (25%) to red (65%). */
export function fgPctColor(pct: number | null | undefined): string {
  if (pct == null) return '#3a3530';
  const t = Math.max(0, Math.min(1, (pct - 0.25) / 0.4));
  const stops = [{ t: 0, c: [58, 111, 158] }, { t: 0.4, c: [106, 138, 90] }, { t: 0.7, c: [217, 154, 62] }, { t: 1, c: [224, 82, 74] }];
  let lo = stops[0], hi = stops[stops.length - 1];
  for (let i = 0; i < stops.length - 1; i++) if (t >= stops[i].t && t <= stops[i + 1].t) { lo = stops[i]; hi = stops[i + 1]; break; }
  const k = (t - lo.t) / ((hi.t - lo.t) || 1);
  const [r, g, b] = lo.c.map((v, i) => Math.round(v + (hi.c[i] - v) * k));
  return `rgb(${r},${g},${b})`;
}

/** Area between two radii, swept from angle a0 to a1 (0 = right baseline, 180 = left). */
export function ringWedgePath(rInner: number, rOuter: number, a0 = 0, a1 = 180, n = 20): string {
  const arc = (r: number, from: number, to: number) => Array.from({ length: n + 1 }, (_, i) => {
    const a = ((from + (to - from) * i / n) * Math.PI) / 180;
    return pt(r * Math.cos(a), r * Math.sin(a));
  });
  const all = rInner > 0 ? [...arc(rOuter, a0, a1), ...arc(rInner, a1, a0)] : [...arc(rOuter, a0, a1), pt(0, 0)];
  return 'M' + all.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L') + ' Z';
}

const R3 = 23.75, CORNER = 22;
const CORNER_DY = Math.sqrt(R3 * R3 - CORNER * CORNER);   // corner line meets the arc ~14.2 ft up

function cornerPath(side: -1 | 1) {
  const [p1, p2, p3, p4] = [pt(side * 18, 0), pt(side * 25, 0), pt(side * 25, CORNER_DY), pt(side * 18, CORNER_DY)];
  return `M${p1} L${p2} L${p3} L${p4} Z`;
}

interface Hover { zone: string; sub: string; fg: number | null; share: number | null; x: number; y: number }

export function Court({ data }: { data: ShootingSeason }) {
  const [hover, setHover] = useState<Hover | null>(null);
  const zone = (label: string, sub: string, share: number | null, fg: number | null, d: string, opacity: number) => (
    <path key={label + sub} className="court-zone" d={d} fill={fgPctColor(fg)} fillOpacity={opacity.toFixed(2)}
          data-zone={label}
          onMouseMove={e => {
            const box = (e.currentTarget.ownerSVGElement!.parentElement!).getBoundingClientRect();
            setHover({ zone: label, sub, fg, share, x: e.clientX - box.left + 14, y: e.clientY - box.top - 10 });
          }}
          onMouseLeave={() => setHover(null)} />
  );
  const [paintA, paintB] = [pt(-8, 0), pt(8, 19)];
  const [raL, raR] = [pt(-4, 0), pt(4, 0)];
  const [cL0, cL1, cR0, cR1] = [pt(-CORNER, 0), pt(-CORNER, CORNER_DY), pt(CORNER, 0), pt(CORNER, CORNER_DY)];
  const ft = pt(0, 19);
  const [bbL, bbR] = [pt(-3, -0.75), pt(3, -0.75)];
  const cornerShare = data.pct_corner_3, cornerFg = data.corner_3_pct;

  return (
    <div style={{ position: 'relative' }} id="pc-court-container">
      <svg viewBox={`0 0 ${W} ${H}`} xmlns="http://www.w3.org/2000/svg">
        <g>
          {ZONES.map(z => {
            const share = data[z.key] as number | null, fg = data[z.pctKey] as number | null;
            return zone(z.label, z.sub, share, fg, ringWedgePath(z.rInner, z.rOuter),
                        share != null ? Math.max(0.35, Math.min(0.95, 0.35 + share * 1.3)) : 0.15);
          })}
          {([-1, 1] as const).map(side => zone('Corner Three', side < 0 ? 'Left corner' : 'Right corner', cornerShare, cornerFg,
            cornerPath(side), cornerShare != null ? Math.max(0.4, Math.min(0.95, 0.4 + cornerShare * 2.2)) : 0.15))}
        </g>
        <g pointerEvents="none">
          <line className="court-line" x1={0} y1={0} x2={W} y2={0} />
          <rect className="court-line" x={Math.min(paintA[0], paintB[0])} y={Math.min(paintA[1], paintB[1])}
                width={Math.abs(paintB[0] - paintA[0])} height={Math.abs(paintB[1] - paintA[1])} />
          <circle className="court-line" cx={ft[0]} cy={ft[1]} r={6 * SCALE} />
          <path className="court-line" d={`M${raL} A${4 * SCALE},${4 * SCALE} 0 0 1 ${raR}`} />
          <line className="court-line" x1={cL0[0]} y1={cL0[1]} x2={cL1[0]} y2={cL1[1]} />
          <line className="court-line" x1={cR0[0]} y1={cR0[1]} x2={cR1[0]} y2={cR1[1]} />
          <path className="court-line" d={`M${cL1} A${R3 * SCALE},${R3 * SCALE} 0 0 1 ${cR1}`} />
          <line className="court-line" x1={bbL[0]} y1={bbL[1]} x2={bbR[0]} y2={bbR[1]} />
          <circle className="court-line" cx={BX} cy={BY} r={0.75 * SCALE} />
        </g>
        <g>
          {ZONES.map(z => {
            const [x, y] = pt(0, (z.rInner + z.rOuter) / 2);
            const fg = data[z.pctKey] as number | null;
            return (
              <g key={z.key}>
                <text className="court-zone-label" x={x} y={y - 3}>{fg != null ? (fg * 100).toFixed(2) + '%' : '\u2014'}</text>
                <text className="court-zone-sublabel" x={x} y={y + 10}>{z.sub}</text>
              </g>
            );
          })}
        </g>
      </svg>
      <div className="shot-tooltip" style={{ opacity: hover ? 1 : 0, left: hover?.x, top: hover?.y }}>
        {hover && (
          <>
            <div className="st-zone">{hover.zone}</div>
            <div className="st-row"><span>{hover.sub}</span></div>
            <div className="st-row"><span>FG%</span><b>{fmtPct(hover.fg, 2)}</b></div>
            <div className="st-row"><span>Share of shots</span><b>{fmtPct(hover.share, 2)}</b></div>
          </>
        )}
      </div>
    </div>
  );
}
