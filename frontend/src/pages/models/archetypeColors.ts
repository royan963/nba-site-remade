// One color per role, shared by the trend chart, chips and player pages.
export const ROLE_COLORS: Record<string, string> = {
  'star-creator': '#ff9d2e', 'scoring-wing': '#e0524a', 'combo-guard': '#d99a5c', 'floor-general': '#c7a54a',
  'spot-up-shooter': '#4a8fb8', 'role-player': '#8a8174', 'stretch-big': '#58b8a8', 'scoring-big': '#a066c8',
  'rebounding-forward': '#6a8a5a', 'rim-protector': '#3f6fa8',
};
export const roleColor = (key: string) => ROLE_COLORS[key] ?? '#8a8174';
