import { describe, expect, it } from 'vitest';
import { dateHeading, groupByDate, kindLabel, otLabel, topLine } from './recentGames';

describe('dateHeading', () => {
  it('writes the weekday and day without shifting across time zones', () => {
    expect(dateHeading('2026-10-22')).toBe('Thu, Oct 22');
    expect(dateHeading('2025-06-22')).toBe('Sun, Jun 22');
    expect(dateHeading('2026-01-01')).toBe('Thu, Jan 1');
  });
});

describe('groupByDate', () => {
  it('groups games under their date, keeping the order given', () => {
    const g = [{ date: '2026-10-22', n: 1 }, { date: '2026-10-22', n: 2 }, { date: '2026-10-21', n: 3 }];
    expect(groupByDate(g)).toEqual([{ date: '2026-10-22', games: [g[0], g[1]] }, { date: '2026-10-21', games: [g[2]] }]);
  });
  it('is empty for no games', () => expect(groupByDate([])).toEqual([]));
});

describe('kindLabel', () => {
  it('names the games that are not ordinary regular-season games', () => {
    expect(kindLabel('playoffs')).toBe('Playoffs');
    expect(kindLabel('play_in')).toBe('Play-In');
    expect(kindLabel('cup_final')).toBe('NBA Cup final');
  });
  it('has no label for a regular-season game', () => expect(kindLabel('regular')).toBeNull());
});

describe('otLabel', () => {
  it('shows overtimes', () => {
    expect(otLabel(0)).toBe('');
    expect(otLabel(null)).toBe('');
    expect(otLabel(1)).toBe('OT');
    expect(otLabel(3)).toBe('3OT');
  });
});

describe('topLine', () => {
  it('summarizes a top scorer', () => {
    expect(topLine({ player_id: 'x', player: 'Nikola Jokić', pts: 31, trb: 12, ast: 9 })).toBe('Nikola Jokić 31 pts');
  });
  it('is null when there is no player data', () => expect(topLine(null)).toBeNull());
});
