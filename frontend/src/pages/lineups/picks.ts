// A lineup in the URL: ?p=jordami01:1996,pippesc01,... (season optional =
// that player's best season). Kept separate so it can be unit-tested.
export interface Pick { player_id: string; season: number | null }

const ID = /^[a-z0-9]{1,16}$/;

export function parsePicks(raw: string | null): Pick[] {
  if (!raw) return [];
  const out: Pick[] = [];
  for (const part of raw.split(',')) {
    const [id, season] = part.trim().split(':');
    if (!ID.test(id ?? '') || out.some(p => p.player_id === id)) continue;
    const n = season ? parseInt(season, 10) : NaN;
    out.push({ player_id: id, season: Number.isFinite(n) && n >= 1947 && n <= 2100 ? n : null });
    if (out.length === 5) break;
  }
  return out;
}

export function formatPicks(picks: Pick[]): string {
  return picks.map(p => (p.season ? `${p.player_id}:${p.season}` : p.player_id)).join(',');
}

export const PRESETS: { label: string; p: string }[] = [
  { label: 'All-time dream five', p: 'johnsma02,jordami01,jamesle01,duncati01,abdulka01' },
  { label: '1996 Bulls (72-10)', p: 'harpero01:1996,jordami01:1996,pippesc01:1996,rodmade01:1996,longllu01:1996' },
  { label: '2017 Warriors', p: 'curryst01:2017,thompkl01:2017,duranke01:2017,greendr01:2017,pachuza01:2017' },
];
