import { describe, expect, it } from 'vitest';

import { buildOptions } from '../src/charts/build.js';
import * as theme from '../src/theme.js';
import { FIXTURE_NAMES, fixture } from './helpers.js';

describe('buildOptions — financial correctness', () => {
  it('revenue+margin: dual axis, margin line on the % axis', () => {
    const o = buildOptions(fixture('revenue_margins'));
    expect(Array.isArray(o.yAxis)).toBe(true);
    expect(o.yAxis).toHaveLength(2);
    expect(o.series.map((s: any) => s.type)).toEqual(['column', 'column', 'line']);
    const margin = o.series[2];
    expect(margin.yAxis).toBe(1); // secondary axis
    expect(o.yAxis[1].title.text).toBe('Net margin (%)');
    expect(o.series[0].color).toBe(theme.PRIMARY);
    expect(o.series[1].color).toBe(theme.SECONDARY);
  });

  it('YoY: single percent axis with a percent label formatter', () => {
    const o = buildOptions(fixture('revenue_yoy'));
    expect(o.yAxis.title.text).toBe('YoY growth (%)');
    expect(o.yAxis.labels.formatter).toMatchObject({ __fn__: 'fmt', opts: { percent: true } });
    expect(o.series[0].data[0]).toBeNull(); // first year has no YoY
  });

  it('event flags become labelled x-axis plotLines', () => {
    const data = fixture('revenue_trend'); // ships a COVID flag on FY2020
    const o = buildOptions(data);
    expect(o.xAxis.plotLines).toHaveLength(1);
    const pl = o.xAxis.plotLines[0];
    expect(pl.value).toBe(data.axis.categories!.indexOf('FY2020'));
    expect(pl.value).toBeGreaterThanOrEqual(0);
    expect(pl.label.text).toBe('COVID');
  });

  it('static shift would offset a series — verified upstream; here data passes through', () => {
    const o = buildOptions(fixture('revenue_trend'));
    expect(o.series[0].type).toBe('line');
    expect(o.series[0].data).toHaveLength(data_len('revenue_trend'));
  });

  it('segments: stacked uses normal stacking and palette colors', () => {
    const o = buildOptions(fixture('segments_stacked'));
    expect(o.series).toHaveLength(5);
    expect(o.series.every((s: any) => s.stacking === 'normal')).toBe(true);
    expect(o.series[0].color).toBe(theme.PALETTE[0]);
    expect(o.series[1].color).toBe(theme.PALETTE[1]);
  });

  it('segments: percent variant uses percent stacking + % axis, no data labels', () => {
    const o = buildOptions(fixture('segments_percent'));
    expect(o.series.every((s: any) => s.stacking === 'percent')).toBe(true);
    expect(o.yAxis.title.text).toBe('Share of revenue (%)');
    expect(o.series[0].dataLabels).toBeUndefined(); // too dense → off
  });

  it('segments: grouped has no stacking', () => {
    const o = buildOptions(fixture('segments_grouped'));
    expect(o.series.every((s: any) => s.stacking === undefined)).toBe(true);
  });

  it('waterfall: native type, sign colors, totals slate, reconciling structure', () => {
    const o = buildOptions(fixture('waterfall'));
    const s = o.series[0];
    expect(s.type).toBe('waterfall');
    expect(s.upColor).toBe(theme.POSITIVE);
    expect(s.color).toBe(theme.NEGATIVE);
    const pts = s.data;
    expect(pts[pts.length - 1].isSum).toBe(true);
    expect(pts[pts.length - 1].color).toBe(theme.TOTAL);
    expect(pts[2].isIntermediateSum).toBe(true);
    expect(pts[1].y).toBeLessThan(0); // cost of revenue subtracts
    expect(o.legend.enabled).toBe(false); // single series
  });

  it('dividend + yield: two axes, bars left / yield line right (opposite)', () => {
    const o = buildOptions(fixture('dividend_yield'));
    expect(o.yAxis).toHaveLength(2);
    expect(o.yAxis[1].opposite).toBe(true);
    expect(o.series[0].type).toBe('column');
    expect(o.series[0].yAxis).toBe(0);
    expect(o.series[1].type).toBe('line');
    expect(o.series[1].yAxis).toBe(1);
  });

  it('earnings surprise: sign drives per-point color + zero baseline', () => {
    const o = buildOptions(fixture('surprise_eps'));
    expect(o.yAxis.plotLines?.[0].value).toBe(0); // zero baseline
    const pts = o.series[0].data as Array<{ y: number; color: string }>;
    for (const p of pts) {
      expect(p.color).toBe(p.y >= 0 ? theme.POSITIVE : theme.NEGATIVE);
    }
  });

  it('estimate vs reported: estimate muted, reported bold, shared $B tooltip', () => {
    const o = buildOptions(fixture('estimate_vs_reported_revenue'));
    expect(o.series.map((s: any) => s.name)).toEqual(['Estimate', 'Reported']);
    expect(o.series[0].color).toBe(theme.ESTIMATE);
    expect(o.series[1].color).toBe(theme.PRIMARY);
    expect(o.series[1].tooltip).toMatchObject({ valuePrefix: '$', valueSuffix: 'B' });
  });

  it('price (candlestick): Stock chrome on, datetime axis, no data labels', () => {
    const o = buildOptions(fixture('price_candlestick'));
    expect(o.series[0].type).toBe('candlestick');
    expect(o.series[0].upColor).toBe(theme.POSITIVE);
    expect(o.rangeSelector.enabled).toBe(true);
    expect(o.navigator.enabled).toBe(true);
    expect(o.xAxis.type).toBe('datetime');
    expect(o.series[0].dataLabels).toBeUndefined();
    expect(o.tooltip.shared).toBe(false); // datetime → not shared
  });

  it('price + revenue: datetime, candlestick + column, fiscal columns sized via pointRange', () => {
    const o = buildOptions(fixture('price_with_revenue'));
    expect(o.xAxis.type).toBe('datetime');
    expect(o.series.map((s: any) => s.type)).toEqual(['candlestick', 'column']);
    expect(o.yAxis).toHaveLength(2);
    expect(o.yAxis[1].opposite).toBe(true);        // price axis on the right
    const rev = o.series[1];
    expect(rev.pointRange).toBeGreaterThan(0);      // merged from opts → column spans the quarter
    expect(rev.opacity).toBe(0.5);
    expect(o.rangeSelector.enabled).toBe(true);     // Stock chrome
  });

  it('price+revenue modes: reaction = markers on earnings date, growth = % line', () => {
    const react = buildOptions(fixture('price_revenue_reaction'));
    expect(react.series[1].type).toBe('line');
    expect(react.series[1].lineWidth).toBe(0);              // markers only (price-reaction view)
    expect(react.series[1].marker.enabled).toBe(true);

    const grow = buildOptions(fixture('price_revenue_growth'));
    expect(grow.yAxis[0].title.text).toBe('Revenue YoY (%)'); // percent axis
    expect(grow.series[1].type).toBe('line');
    expect(grow.series[1].marker.radius).toBeGreaterThanOrEqual(4); // prominent dots
  });

  it('multi-company price comparison: rebased lines on a datetime axis', () => {
    const o = buildOptions(fixture('compare_price_rebased'));
    expect(o.xAxis.type).toBe('datetime');
    expect(o.series.map((s: any) => s.type)).toEqual(['line', 'line']);
    expect(o.yAxis.title.text).toBe('Indexed (base 100)');
    expect(o.series[0].data[0][1]).toBe(100); // rebased to 100 at the start
  });

  it('rebased comparison: two lines on an index axis (not percent)', () => {
    const o = buildOptions(fixture('compare_rebased'));
    expect(o.series).toHaveLength(2);
    expect(o.series.every((s: any) => s.type === 'line')).toBe(true);
    expect(o.yAxis.title.text).toBe('Indexed (base 100)');
  });

  it('EPS axis is fixed to 2 decimals (per-share convention)', () => {
    const o = buildOptions(fixture('estimate_vs_reported_eps'));
    expect(o.yAxis.title.text).toBe('EPS ($)');
    expect(o.yAxis.labels.formatter.opts.decimals).toBe(2);
    expect(o.series[0].tooltip.valueDecimals).toBe(2);
  });

  it('every fixture builds a valid options object', () => {
    for (const name of FIXTURE_NAMES) {
      const o = buildOptions(fixture(name));
      expect(o.series.length, name).toBeGreaterThan(0);
      expect(o.xAxis, name).toBeDefined();
      expect(o.title.text, name).toBeTruthy();
    }
  });

  it('stacked panes: yAxis opts (top/height) pass through; arearange band maps natively', () => {
    const o = buildOptions({
      title: 'AAPL — technicals',
      axis: { type: 'datetime' },
      yAxes: [
        { id: 'price', name: 'Price', currency: '$', decimals: 2, opts: { top: '0%', height: '70%' } },
        { id: 'rsi', name: 'RSI', opts: { top: '72%', height: '28%', plotBands: [{ from: 30, to: 70 }] } },
      ],
      series: [
        { name: 'Price', kind: 'candlestick', yAxis: 'price', role: 'primary', data: [[0, 1, 2, 0.5, 1.5]] },
        { name: 'BB', kind: 'arearange', yAxis: 'price', role: 'neutral', data: [[0, 0.8, 1.8]] },
        { name: 'RSI(14)', kind: 'line', yAxis: 'rsi', role: 'secondary', data: [[0, 55]] },
      ],
      meta: { stock: true },
    });
    expect(o.yAxis[0]).toMatchObject({ top: '0%', height: '70%' });
    expect(o.yAxis[1]).toMatchObject({ top: '72%', height: '28%' });
    expect(o.yAxis[1].plotBands).toHaveLength(1);
    expect(o.series[1].type).toBe('arearange');
    expect(o.series[2].yAxis).toBe(1); // RSI series bound to its pane
  });
});

function data_len(name: string): number {
  return fixture(name).series[0].data.length;
}
