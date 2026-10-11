import { describe, expect, it } from 'vitest';
import { layoutMarkers, slugify } from './geo';

const marker = (x: number, y: number) => ({ trueX: x, trueY: y, x, y, offset: false });

describe('slugify', () => {
  it('makes URL-safe franchise slugs', () => {
    expect(slugify('Boston Celtics')).toBe('boston-celtics');
    expect(slugify('Baltimore Bullets (original)')).toBe('baltimore-bullets-original');
    expect(slugify('Philadelphia 76ers')).toBe('philadelphia-76ers');
  });
});

describe('layoutMarkers', () => {
  it('fans out teams in the same city', () => {
    const [lakers, clippers] = layoutMarkers([marker(100, 100), marker(100, 100)]);
    expect(Math.hypot(lakers.x - clippers.x, lakers.y - clippers.y)).toBeGreaterThanOrEqual(38 * 0.99);
    expect(lakers.offset && clippers.offset).toBe(true);
  });
  it('leaves isolated teams exactly where they are', () => {
    const [a, b] = layoutMarkers([marker(0, 0), marker(500, 500)]);
    expect([a.x, a.y, a.offset]).toEqual([0, 0, false]);
    expect([b.x, b.y]).toEqual([500, 500]);
  });
  it('separates a dense cluster', () => {
    const pts = layoutMarkers([marker(300, 300), marker(310, 305), marker(305, 315), marker(320, 300)]);
    for (let i = 0; i < pts.length; i++)
      for (let j = i + 1; j < pts.length; j++)
        expect(Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y)).toBeGreaterThan(30);
  });
  it('is deterministic', () => {
    const run = () => layoutMarkers([marker(5, 5), marker(5, 5), marker(5, 5)]).map(m => [m.x.toFixed(3), m.y.toFixed(3)]);
    expect(run()).toEqual(run());
  });
});
