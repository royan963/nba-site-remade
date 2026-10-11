import { describe, expect, it } from 'vitest';
import { formatPicks, parsePicks } from './picks';

describe('lineup picks in the URL', () => {
  it('round-trips', () => {
    const raw = 'jordami01:1996,pippesc01,rodmade01:1996';
    expect(formatPicks(parsePicks(raw))).toBe(raw);
  });
  it('ignores junk, duplicates and anything past five players', () => {
    const picks = parsePicks('jordami01,<script>,jordami01,a,b,c,d,e:1900,f');
    expect(picks.map(p => p.player_id)).toEqual(['jordami01', 'a', 'b', 'c', 'd']);
    expect(parsePicks('x:1900')[0].season).toBeNull();
    expect(parsePicks(null)).toEqual([]);
  });
});
