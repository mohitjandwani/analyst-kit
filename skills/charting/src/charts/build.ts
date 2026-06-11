/**
 * The chart builder: final-data → Highcharts options.
 *
 * One generic builder, because the contract already carries every per-chart
 * decision (series `kind`, semantic `role`, `meta.variant` for stacking,
 * `meta.stock` for Stock chrome, `meta.zeroLine`). Named wrappers in index.ts give
 * each chart an ergonomic entry point. Output is a plain object with serializable
 * formatter *descriptors* (see format.ts); render.ts hydrates those into functions.
 */
import { fmtRef } from '../format.js';
import {
  AXIS_LABEL, BACKGROUND, NEGATIVE, PALETTE, POSITIVE, SPLIT_LINE, TOTAL,
  colorForIndex, colorForRole,
} from '../theme.js';
import type { BuildOpts, ChartOptions, FinalData, SeriesSpec, YAxisSpec } from '../types.js';

const HC_TYPE: Record<string, string> = {
  line: 'line', column: 'column', area: 'area', arearange: 'arearange',
  waterfall: 'waterfall', candlestick: 'candlestick',
};

function axisTitle(a: YAxisSpec): string {
  if (a.percent) return `${a.name} (%)`;
  const unit = `${a.currency ?? ''}${a.unit ?? ''}`;
  return unit ? `${a.name} (${unit})` : a.name;
}

function mapData(s: SeriesSpec): unknown[] {
  if (s.kind === 'waterfall') {
    return s.data.map((pt) => {
      const p = pt as any;
      if (p.isSum) return { name: p.name, isSum: true, color: TOTAL };
      if (p.isIntermediateSum) return { name: p.name, isIntermediateSum: true, color: TOTAL };
      return { name: p.name, y: p.y };
    });
  }
  return s.data.map((pt) => {
    if (pt === null) return null;
    if (typeof pt === 'number' || Array.isArray(pt)) return pt;
    const p = pt as any;
    if (s.role === 'signed') return { y: p.y, color: p.role === 'positive' ? POSITIVE : NEGATIVE };
    return p;
  });
}

export function buildOptions(d: FinalData, opts: BuildOpts = {}): ChartOptions {
  const isDatetime = d.axis.type === 'datetime';
  const useStock = opts.stock ?? !!d.meta?.stock;

  // --- x axis (+ caller event flags as plotLines) ---
  const xAxis: ChartOptions = isDatetime
    ? { type: 'datetime' }
    : { type: 'category', categories: d.axis.categories ?? [] };
  if (d.flags?.length) {
    xAxis.plotLines = d.flags
      .map((f) => ({
        value: isDatetime ? Number(f.x) : (d.axis.categories ?? []).indexOf(String(f.x)),
        color: NEGATIVE, dashStyle: 'Dash', width: 1, zIndex: 5,
        label: { text: f.title, rotation: 0, y: 14, style: { color: AXIS_LABEL, fontSize: '10px' } },
      }))
      .filter((pl) => isDatetime || pl.value >= 0);
  }

  // --- y axes ---
  const yAxes = d.yAxes.map((a) => {
    const ax: ChartOptions = {
      title: { text: axisTitle(a), style: { color: AXIS_LABEL } },
      labels: { formatter: fmtRef({ currency: a.currency, unit: a.unit, percent: a.percent, decimals: a.decimals }), style: { color: AXIS_LABEL } },
      opposite: !!a.opposite,
      gridLineColor: SPLIT_LINE,
    };
    if (a.percent && d.meta?.zeroLine) {
      ax.plotLines = [{ value: 0, color: AXIS_LABEL, width: 1, zIndex: 3 }];
    }
    // passthrough Highcharts yAxis options from the contract (top/height for panes, plotBands…)
    if (a.opts) Object.assign(ax, a.opts);
    return ax;
  });

  // --- series ---
  let segIdx = 0;
  const labelableChart = !isDatetime && d.series.length <= 3 && d.meta?.variant !== 'percent';
  const series = d.series.map((s) => {
    const axisSpec = d.yAxes.find((a) => a.id === s.yAxis);
    const out: ChartOptions = { name: s.name, type: HC_TYPE[s.kind] ?? 'line', data: mapData(s) };

    if (d.yAxes.length > 1 && s.yAxis) out.yAxis = d.yAxes.findIndex((a) => a.id === s.yAxis);

    // color by role (segments cycle the palette; signed/waterfall color per point)
    if (s.role === 'segment') out.color = colorForIndex(segIdx++);
    else if (s.kind === 'waterfall') { out.upColor = POSITIVE; out.color = NEGATIVE; }
    else if (s.kind === 'candlestick') { out.upColor = POSITIVE; out.color = NEGATIVE; out.upLineColor = POSITIVE; out.lineColor = NEGATIVE; }
    else if (s.role !== 'signed') out.color = colorForRole(s.role);

    if (s.role === 'estimate' && s.kind === 'line') out.dashStyle = 'Dash';

    // stacking for segment columns
    if (s.kind === 'column' && d.meta?.variant === 'stacked') out.stacking = 'normal';
    else if (s.kind === 'column' && d.meta?.variant === 'percent') out.stacking = 'percent';

    // tooltip value formatting — static strings, no function needed
    if (axisSpec?.percent) out.tooltip = { valueSuffix: '%', valueDecimals: axisSpec.decimals ?? 1 };
    else if (axisSpec) out.tooltip = { valuePrefix: axisSpec.currency ?? '', valueSuffix: axisSpec.unit ?? '', valueDecimals: axisSpec.decimals ?? 1 };

    // compact data labels, per-need
    if (opts.dataLabels ?? labelableChart) {
      out.dataLabels = {
        enabled: true,
        formatter: fmtRef({ currency: axisSpec?.currency, unit: axisSpec?.unit, percent: axisSpec?.percent, decimals: axisSpec?.decimals }),
        style: { fontSize: '9px', fontWeight: 'normal', textOutline: 'none' },
      };
    }

    // passthrough Highcharts series options from the contract (pointRange, opacity, zIndex…)
    if (s.opts) Object.assign(out, s.opts);
    return out;
  });

  // --- assemble ---
  const options: ChartOptions = {
    chart: { backgroundColor: BACKGROUND, style: { fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' } },
    title: { text: d.title, style: { fontSize: '16px', fontWeight: '600' } },
    colors: PALETTE,
    credits: { enabled: false },
    legend: { enabled: d.series.length > 1 },
    tooltip: { shared: !isDatetime },
    xAxis,
    yAxis: yAxes.length === 1 ? yAxes[0] : yAxes,
    series,
    plotOptions: { series: { animation: false } },
  };
  if (d.subtitle) options.subtitle = { text: d.subtitle, style: { color: AXIS_LABEL } };

  if (useStock) {
    options.rangeSelector = {
      enabled: opts.rangeSelector ?? true,
      selected: 5,
      buttons: [
        { type: 'month', count: 1, text: '1m' },
        { type: 'month', count: 3, text: '3m' },
        { type: 'month', count: 6, text: '6m' },
        { type: 'ytd', text: 'YTD' },
        { type: 'year', count: 1, text: '1y' },
        { type: 'all', text: 'All' },
      ],
    };
    options.navigator = { enabled: opts.navigator ?? true };
    options.scrollbar = { enabled: false };
  }
  return options;
}
