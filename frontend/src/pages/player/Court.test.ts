import { describe, expect, it } from 'vitest';
import { fgPctColor, ringWedgePath } from './Court';

describe('court', () => {
  it('colors the FG% scale from cool to hot', () => {
    expect(fgPctColor(0.25)).toBe('rgb(58,111,158)');
    expect(fgPctColor(0.65)).toBe('rgb(224,82,74)');
    expect(fgPctColor(0.9)).toBe('rgb(224,82,74)');     // clamped
    expect(fgPctColor(null)).toBe('#3a3530');
  });
  it('builds closed zone paths', () => {
    const d = ringWedgePath(4, 10);
    expect(d.startsWith('M')).toBe(true);
    expect(d.endsWith('Z')).toBe(true);
    expect(d.split('L').length).toBe(42);              // 21 outer + 21 inner points
  });
});
