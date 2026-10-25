// Small helpers for the "Recent games" section.

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-10-22" -> "Thu, Oct 22". Read as a calendar date (UTC), so the viewer's time zone can't move it a day. */
export function dateHeading(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  const day = new Date(Date.UTC(y, m - 1, d));
  return `${WEEKDAYS[day.getUTCDay()]}, ${MONTHS[m - 1]} ${d}`;
}

/** Group consecutive items by their `date`, keeping the order given. */
export function groupByDate<T extends { date: string }>(items: T[]): { date: string; games: T[] }[] {
  const out: { date: string; games: T[] }[] = [];
  for (const it of items) {
    const last = out[out.length - 1];
    if (last && last.date === it.date) last.games.push(it);
    else out.push({ date: it.date, games: [it] });
  }
  return out;
}

/** A badge for games that are not ordinary regular-season games; null for a regular-season game. */
export function kindLabel(kind: string): string | null {
  return ({ playoffs: 'Playoffs', play_in: 'Play-In', cup_final: 'NBA Cup final' } as Record<string, string>)[kind] ?? null;
}

export const otLabel = (ot: number | null | undefined): string => (!ot ? '' : ot === 1 ? 'OT' : `${ot}OT`);

export function topLine<T extends { player: string; pts: number | null }>(top: T | null): string | null {
  return top && top.pts != null ? `${top.player} ${top.pts} pts` : null;
}
