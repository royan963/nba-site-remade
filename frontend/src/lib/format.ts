const ok = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

export const DASH = '\u2014';
export const fmtNum = (v: number | null | undefined, d = 1) => (ok(v) ? v.toFixed(d) : DASH);
export const fmtInt = (v: number | null | undefined) => (ok(v) ? Math.round(v).toLocaleString('en-US') : DASH);
/** fraction (0.393) -> "39.3%" */
export const fmtPct = (v: number | null | undefined, d = 1) => (ok(v) ? (v * 100).toFixed(d) + '%' : DASH);
export const fmtSigned = (v: number | null | undefined, d = 1) => (ok(v) ? (v > 0 ? '+' : '') + v.toFixed(d) : DASH);

export type StatFormat = 'num' | 'pct' | 'int' | 'idx' | 'num3' | 'signed';

export function formatStat(fmt: StatFormat, v: number | null | undefined): string {
  if (!ok(v)) return DASH;
  switch (fmt) {
    case 'pct': return (v * 100).toFixed(2) + '%';
    case 'int': return Math.round(v).toLocaleString('en-US');
    case 'idx': return Math.round(v).toString();
    case 'num3': return v.toFixed(3);
    case 'signed': return fmtSigned(v);
    default: return v.toFixed(1);
  }
}

/** Value for a chart axis: percentages plotted as 0-100. */
export const chartValue = (fmt: StatFormat, v: number | null | undefined) => (ok(v) ? (fmt === 'pct' ? v * 100 : v) : null);

export const height = (inches: number | null) => (inches ? `${Math.floor(inches / 12)}'${inches % 12}"` : DASH);
