// Small helpers for the "each role" trend charts: one shared scale, a point list, SVG paths, and hover lookup.

/** Largest share across every role, rounded up to a clean 5% step, so all the small charts use one vertical scale. */
export function sharedMax(series: number[][]): number {
  const m = Math.max(0, ...series.map(s => Math.max(0, ...s)));
  return Math.max(5, Math.ceil(m / 5) * 5);
}

/** The season with the largest share (the earliest on a tie), or null with no data. */
export function peakOf(seasons: number[], values: number[]): { season: number; value: number } | null {
  let best = -1;
  values.forEach((v, i) => { if (best < 0 || v > values[best]) best = i; });
  return best < 0 ? null : { season: seasons[best], value: values[best] };
}

/** Points across `width`, with `max` at the top (y = 0) and zero at the bottom (y = height). */
export function sparkPoints(values: number[], width: number, height: number, max: number): [number, number][] {
  const n = values.length;
  return values.map((v, i) => [n === 1 ? 0 : (i / (n - 1)) * width, height - (v / max) * height] as [number, number]);
}

const round = (v: number) => Math.round(v * 10) / 10;

export const linePath = (pts: [number, number][]): string => (pts.length ? 'M' + pts.map(p => `${round(p[0])},${round(p[1])}`).join(' L') : '');

export function areaPath(pts: [number, number][], height: number): string {
  if (!pts.length) return '';
  const last = pts[pts.length - 1];
  const first = pts[0];
  return `${linePath(pts)} L${round(last[0])},${height} L${round(first[0])},${height} Z`;
}

/** Index of the season closest to a pointer at `x` (0..width) on a chart with `n` seasons. */
export function nearestIndex(x: number, width: number, n: number): number {
  if (n <= 1 || width <= 0) return 0;
  return Math.min(n - 1, Math.max(0, Math.round((x / width) * (n - 1))));
}

/** 1988 -> "1987-88": seasons are labeled by the year they end. */
export const seasonLabel = (season: number): string => `${season - 1}-${String(season).slice(-2)}`;

export interface Slice { start: number; end: number; mid: number; fraction: number }

/** Pie slices as angles (radians): start at the top, run clockwise, each as wide as its share of the total. */
export function pieSlices(values: number[]): Slice[] {
  const total = values.reduce((a, b) => a + Math.max(0, b), 0);
  let angle = -Math.PI / 2;
  return values.map(v => {
    const fraction = total > 0 ? Math.max(0, v) / total : 0;
    const start = angle;
    angle += fraction * Math.PI * 2;
    return { start, end: angle, mid: (start + angle) / 2, fraction };
  });
}

export const polar = (cx: number, cy: number, r: number, angle: number): [number, number] => [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];

/** A ring segment between radii r0 (hole) and r1 (edge) from angle a0 to a1; a whole ring when it spans the full circle. */
export function arcPath(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const span = a1 - a0;
  if (span <= 1e-9) return '';
  const pt = (r: number, a: number) => polar(cx, cy, r, a).map(round).join(',');
  if (span >= Math.PI * 2 - 1e-6) {
    const mid = a0 + Math.PI;
    return `M${pt(r1, a0)} A${r1},${r1} 0 1 1 ${pt(r1, mid)} A${r1},${r1} 0 1 1 ${pt(r1, a0)} M${pt(r0, a0)} A${r0},${r0} 0 1 0 ${pt(r0, mid)} A${r0},${r0} 0 1 0 ${pt(r0, a0)} Z`;
  }
  const large = span > Math.PI ? 1 : 0;
  return `M${pt(r1, a0)} A${r1},${r1} 0 ${large} 1 ${pt(r1, a1)} L${pt(r0, a1)} A${r0},${r0} 0 ${large} 0 ${pt(r0, a0)} Z`;
}

/** Y-axis tick values from 0 up to max: steps of 5 for small scales, 10 for larger. */
export function yTicks(max: number): number[] {
  const step = max <= 20 ? 5 : 10;
  const out: number[] = [];
  for (let v = 0; v <= max + 1e-9; v += step) out.push(v);
  return out;
}

/** The decade years (1960, 1970, ...) that fall inside the seasons shown. */
export function decadeTicks(seasons: number[]): number[] {
  return seasons.filter(s => s % 10 === 0);
}
