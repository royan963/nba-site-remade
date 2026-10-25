import { describe, expect, it } from 'vitest';
import { areaPath, linePath, nearestIndex, peakOf, sharedMax, sparkPoints } from './archetypeTrend';

describe('sharedMax', () => {
  it('rounds the largest share up to a clean 5% step so every role uses one scale', () => {
    expect(sharedMax([[1, 12.3], [30.2, 4]])).toBe(35);
    expect(sharedMax([[10], [20]])).toBe(20);
  });
  it('never returns zero', () => expect(sharedMax([[0, 0]])).toBe(5));
});

describe('peakOf', () => {
  it('finds the season with the largest share, the earliest on a tie', () => {
    expect(peakOf([1990, 1991, 1992], [5, 9, 9])).toEqual({ season: 1991, value: 9 });
  });
  it('is null for no data', () => expect(peakOf([], [])).toBeNull());
});

describe('sparkPoints', () => {
  it('spreads values across the width and puts the shared maximum at the top', () => {
    expect(sparkPoints([0, 10, 20], 100, 50, 20)).toEqual([[0, 50], [50, 25], [100, 0]]);
  });
  it('handles a single value', () => expect(sparkPoints([10], 100, 50, 20)).toEqual([[0, 25]]));
});

describe('paths', () => {
  const pts: [number, number][] = [[0, 50], [50, 25], [100, 0]];
  it('draws a line through the points', () => expect(linePath(pts)).toBe('M0,50 L50,25 L100,0'));
  it('closes the area down to the baseline', () => expect(areaPath(pts, 50)).toBe('M0,50 L50,25 L100,0 L100,50 L0,50 Z'));
  it('is empty with no points', () => { expect(linePath([])).toBe(''); expect(areaPath([], 50)).toBe(''); });
});

describe('nearestIndex', () => {
  it('maps a pointer position to the closest season', () => {
    expect(nearestIndex(0, 100, 5)).toBe(0);
    expect(nearestIndex(100, 100, 5)).toBe(4);
    expect(nearestIndex(51, 100, 5)).toBe(2);
  });
  it('clamps outside the chart', () => {
    expect(nearestIndex(-20, 100, 5)).toBe(0);
    expect(nearestIndex(500, 100, 5)).toBe(4);
  });
});

import { arcPath, decadeTicks, pieSlices, polar, seasonLabel, yTicks } from './archetypeTrend';

describe('seasonLabel', () => {
  it('writes a season by its two years', () => {
    expect(seasonLabel(1988)).toBe('1987-88');
    expect(seasonLabel(2000)).toBe('1999-00');
    expect(seasonLabel(2026)).toBe('2025-26');
  });
});

describe('pieSlices', () => {
  const TAU = Math.PI * 2;
  it('starts at the top and runs clockwise, each slice as wide as its share', () => {
    const s = pieSlices([50, 25, 25]);
    expect(s[0].start).toBeCloseTo(-Math.PI / 2);
    expect(s[0].end - s[0].start).toBeCloseTo(TAU / 2);
    expect(s[1].start).toBeCloseTo(s[0].end);
    expect(s[2].end).toBeCloseTo(-Math.PI / 2 + TAU);
    expect(s.map(x => x.fraction)).toEqual([0.5, 0.25, 0.25]);
  });
  it('rescales shares that do not add to exactly 100', () => {
    const s = pieSlices([40, 40]);
    expect(s[1].end).toBeCloseTo(-Math.PI / 2 + TAU);
  });
  it('gives an empty slice zero width and survives all zeros', () => {
    expect(pieSlices([10, 0, 10])[1].end - pieSlices([10, 0, 10])[1].start).toBe(0);
    expect(pieSlices([0, 0]).every(x => x.fraction === 0)).toBe(true);
  });
  it('puts the middle angle halfway through each slice', () => {
    const s = pieSlices([50, 50]);
    expect(s[0].mid).toBeCloseTo((s[0].start + s[0].end) / 2);
  });
});

describe('polar and arcPath', () => {
  it('converts an angle to a point', () => {
    const [x, y] = polar(0, 0, 10, -Math.PI / 2);
    expect(x).toBeCloseTo(0);
    expect(y).toBeCloseTo(-10);
  });
  it('draws a ring segment: out along the edge, in along the hole', () => {
    expect(arcPath(0, 0, 50, 100, -Math.PI / 2, 0)).toBe('M0,-100 A100,100 0 0 1 100,0 L50,0 A50,50 0 0 0 0,-50 Z');
  });
  it('uses the large-arc flag for a segment over half the circle', () => {
    expect(arcPath(0, 0, 50, 100, -Math.PI / 2, Math.PI)).toContain('A100,100 0 1 1');
  });
  it('draws a whole ring when one slice is everything', () => {
    const d = arcPath(0, 0, 50, 100, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2);
    expect(d.startsWith('M')).toBe(true);
    expect((d.match(/A100,100/g) ?? []).length).toBe(2);
  });
  it('is empty for a zero-width slice', () => expect(arcPath(0, 0, 50, 100, 1, 1)).toBe(''));
});

describe('axis ticks', () => {
  it('picks y ticks in steps of 5 for small scales and 10 for large ones', () => {
    expect(yTicks(15)).toEqual([0, 5, 10, 15]);
    expect(yTicks(30)).toEqual([0, 10, 20, 30]);
    expect(yTicks(100)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
  });
  it('lists the decades inside the seasons shown', () => {
    expect(decadeTicks([1952, 1953, 1960, 1975, 1999, 2026])).toEqual([1960]);
    expect(decadeTicks(Array.from({ length: 75 }, (_, i) => 1952 + i))).toEqual([1960, 1970, 1980, 1990, 2000, 2010, 2020]);
  });
});
