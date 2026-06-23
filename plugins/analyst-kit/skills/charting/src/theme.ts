/**
 * Visual language: colorblind-safe categorical palette + semantic role→color map.
 * Green = up/gain/beat, red = down/loss/miss (US/EU convention); estimates muted,
 * totals dark slate. Neutral light theme, no dark mode in v1.
 */

/** Categorical palette for segments / multiple series (vivid, modern). */
export const PALETTE = [
  '#5B8FF9', '#5AD8A6', '#F6BD16', '#7262FD',
  '#F6903D', '#78D3F8', '#9661BC', '#269A99',
];

export const POSITIVE = '#45B7A0'; // teal-green — gains, beats, up/start in waterfall
export const NEGATIVE = '#EE6677'; // rose-red — losses, misses, down deltas
export const PRIMARY = '#5B8FF9';  // cornflower blue — main level series (revenue, reported)
export const SECONDARY = '#5AD8A6'; // mint — paired level series (net income, dividend)
export const NEUTRAL = '#7262FD';  // purple — overlaid line (margin, yield), stands out over bars
export const ESTIMATE = '#BFC6D4'; // muted grey-blue — consensus / forecast
export const TOTAL = '#5B8FF9';    // blue — waterfall sums / subtotals

export const AXIS_LABEL = '#666666';
export const SPLIT_LINE = '#ECECEC';
export const BACKGROUND = '#FFFFFF';

const ROLE_COLOR: Record<string, string> = {
  primary: PRIMARY,
  secondary: SECONDARY,
  neutral: NEUTRAL,
  positive: POSITIVE,
  negative: NEGATIVE,
  estimate: ESTIMATE,
  total: TOTAL,
};

/** Color for a non-categorical role; segments are colored by index instead. */
export function colorForRole(role: string): string {
  return ROLE_COLOR[role] ?? PRIMARY;
}

/** Cycle the categorical palette for the i-th segment / company. */
export function colorForIndex(i: number): string {
  return PALETTE[i % PALETTE.length];
}
