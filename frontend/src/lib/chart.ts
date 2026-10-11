import { Chart, registerables, type ChartOptions } from 'chart.js';

Chart.register(...registerables);
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.color = '#b7afa0';
Chart.defaults.borderColor = 'rgba(241,235,224,0.08)';

export const PALETTE = {
  amber: '#ff9d2e',
  amberDim: 'rgba(255,157,46,0.15)',
  blue: '#4a8fb8',
  blueDim: 'rgba(74,143,184,0.15)',
  wood: '#d99a5c',
  chalk: '#f1ebe0',
  chalkDim: '#b7afa0',
  grid: 'rgba(241,235,224,0.07)',
};

export const MONO = { family: "'JetBrains Mono', monospace", size: 11 };

export const TOOLTIP = {
  backgroundColor: '#1f1a16',
  borderColor: 'rgba(241,235,224,0.18)',
  borderWidth: 1,
  titleFont: { family: MONO.family, size: 12 },
  bodyFont: { family: MONO.family, size: 12 },
  padding: 10,
  titleColor: PALETTE.amber,
  bodyColor: PALETTE.chalk,
};

/** Shared look for every chart. `extra` replaces top-level keys (like the original app). */
export function baseOptions(extra: Record<string, unknown> = {}): ChartOptions {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { labels: { color: PALETTE.chalkDim, font: MONO, boxWidth: 12, boxHeight: 12 } },
      tooltip: TOOLTIP,
    },
    scales: {
      x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, font: { size: 11 } } },
      y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, font: { size: 11 } } },
    },
    ...extra,
  } as ChartOptions;
}

export const axis = (extra: Record<string, unknown> = {}) => ({
  grid: { color: PALETTE.grid },
  ticks: { color: PALETTE.chalkDim, ...(extra.ticks as object || {}) },
  ...Object.fromEntries(Object.entries(extra).filter(([k]) => k !== 'ticks')),
});

export { Chart };
