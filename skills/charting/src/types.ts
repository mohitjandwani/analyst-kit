/**
 * The chart contract (see SKILL.md) — what the Python + Polars layer emits and the
 * Highcharts builders consume. Numbers arrive already scaled to one unit per axis;
 * series are tagged with a semantic `role` that maps to a color here.
 */

export type Role =
  | 'primary' | 'secondary' | 'neutral'
  | 'positive' | 'negative' | 'estimate' | 'total'
  | 'segment' | 'signed' | 'waterfall';

export type SeriesKind = 'line' | 'column' | 'area' | 'waterfall' | 'candlestick';

export interface YAxisSpec {
  id: string;
  name: string;
  unit?: string;       // scale suffix: 'B' | 'M' | 'K' | ''
  currency?: string;   // '$' | '€' | …
  percent?: boolean;
  opposite?: boolean;  // secondary axis on the right
  decimals?: number;   // fixed decimals (e.g. 2 for EPS/per-share); omit = convention default
}

export interface AxisSpec {
  type: 'category' | 'datetime';
  categories?: string[];
}

/** A point may be a bare number, a [ts, …] tuple (datetime), or a tagged object. */
export type DataPoint =
  | number
  | null
  | number[]
  | { y?: number; name?: string; role?: Role; isSum?: boolean; isIntermediateSum?: boolean };

export interface SeriesSpec {
  name: string;
  kind: SeriesKind;
  yAxis?: string;      // YAxisSpec.id
  role: Role;
  data: DataPoint[];
  /** Extra Highcharts series options merged verbatim (e.g. pointRange, opacity, zIndex). */
  opts?: Record<string, any>;
}

export interface EventFlag {
  x: string | number;  // category label (category axis) or epoch ms (datetime axis)
  title: string;
}

export interface FinalData {
  title: string;
  subtitle?: string;
  axis: AxisSpec;
  yAxes: YAxisSpec[];
  series: SeriesSpec[];
  flags?: EventFlag[];
  meta: Record<string, unknown> & {
    chart?: string;
    variant?: 'stacked' | 'percent' | 'grouped';
    stock?: boolean;
    zeroLine?: boolean;
    currency?: string;
    unit?: string;
  };
}

/** Loose Highcharts options — we don't depend on the highcharts package for types. */
export type ChartOptions = Record<string, any>;

export interface BuildOpts {
  /** Use Highcharts Stock (navigator + rangeSelector). Defaults to meta.stock. */
  stock?: boolean;
  rangeSelector?: boolean;
  navigator?: boolean;
  /** On-chart data labels. Defaults on for category charts, off for datetime. */
  dataLabels?: boolean;
}
