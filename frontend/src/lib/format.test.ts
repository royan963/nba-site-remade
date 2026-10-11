import { describe, expect, it } from 'vitest';
import { formatStat, fmtPct, height } from './format';

describe('formatStat', () => {
  it('formats each stat type', () => {
    expect(formatStat('pct', 0.3934)).toBe('39.34%');
    expect(formatStat('int', 1234.4)).toBe('1,234');
    expect(formatStat('idx', 209.6)).toBe('210');
    expect(formatStat('num3', 0.2421)).toBe('0.242');
    expect(formatStat('signed', 7.66)).toBe('+7.7');
    expect(formatStat('num', 30)).toBe('30.0');
  });
  it('shows a dash for missing values', () => {
    expect(formatStat('pct', null)).toBe('\u2014');
    expect(fmtPct(undefined)).toBe('\u2014');
    expect(formatStat('num', NaN)).toBe('\u2014');
  });
  it('formats height', () => expect(height(74)).toBe(`6'2"`));
});
