import { formatStat, type StatFormat } from '../../lib/format';

export interface StatRowDef { key: string; label: string; fmt: StatFormat; lowerBetter?: boolean }

/** Two-sided bar row: A's bar grows left, B's grows right; the better value is highlighted. */
export function StatBarRow({ def, a, b }: { def: StatRowDef; a: number | null | undefined; b: number | null | undefined }) {
  const ok = (v: number | null | undefined): v is number => v != null && Number.isFinite(v);
  const max = Math.max(ok(a) ? Math.abs(a) : 0, ok(b) ? Math.abs(b) : 0, 0.001);
  const wA = ok(a) ? Math.max(4, (Math.abs(a) / max) * 100) : 0;
  const wB = ok(b) ? Math.max(4, (Math.abs(b) / max) * 100) : 0;
  const both = ok(a) && ok(b) && a !== b;
  const aWins = both && (def.lowerBetter ? a! < b! : a! > b!);
  const bWins = both && !aWins;
  return (
    <div className={`cmp-stat-row ${aWins ? 'cmp-stat-winner-a' : ''} ${bWins ? 'cmp-stat-winner-b' : ''}`}>
      <div className="cmp-stat-bar-wrap right">
        <span className="cmp-stat-value a-val">{formatStat(def.fmt, a)}</span>
        <div className="cmp-stat-bar-track"><div className="cmp-stat-bar-fill a" style={{ width: `${wA}%` }} /></div>
      </div>
      <span className="cmp-stat-label">{def.label}</span>
      <div className="cmp-stat-bar-wrap">
        <div className="cmp-stat-bar-track"><div className="cmp-stat-bar-fill b" style={{ width: `${wB}%` }} /></div>
        <span className="cmp-stat-value b-val">{formatStat(def.fmt, b)}</span>
      </div>
    </div>
  );
}
