import { describe, expect, it } from 'vitest';

import { optionsToJs, renderChartPage, scriptsFor } from '../src/render.js';
import { fixture } from './helpers.js';

describe('optionsToJs', () => {
  it('hydrates a formatter descriptor into a real function', () => {
    const js = optionsToJs({ formatter: { __fn__: 'fmt', opts: { currency: '$', unit: 'B' } } });
    expect(js).toContain('function()');
    expect(js).toContain('AK.fmt');
    expect(js).toContain('"currency":"$"');
  });

  it('serializes plain values like JSON', () => {
    expect(optionsToJs({ a: 1, b: 'x', c: [true, null] })).toBe('{"a":1,"b":"x","c":[true,null]}');
  });

  it('omits undefined keys', () => {
    expect(optionsToJs({ a: 1, b: undefined })).toBe('{"a":1}');
  });
});

describe('scriptsFor', () => {
  it('uses Highstock for stock charts, core otherwise; loads from jsDelivr', () => {
    expect(scriptsFor(false)[0]).toBe('https://cdn.jsdelivr.net/npm/highcharts@12/highcharts.js');
    expect(scriptsFor(true)[0]).toBe('https://cdn.jsdelivr.net/npm/highcharts@12/highstock.js');
    expect(scriptsFor(false).some((s) => s.includes('accessibility'))).toBe(true);
  });

  it('adds highcharts-more.js only when a waterfall is present', () => {
    expect(scriptsFor(false, true).some((s) => s.includes('highcharts-more'))).toBe(true);
    expect(scriptsFor(false, false).some((s) => s.includes('highcharts-more'))).toBe(false);
  });

  it('arearange (e.g. Bollinger band) also pulls in highcharts-more', () => {
    const html = renderChartPage(
      {
        title: 'band',
        axis: { type: 'datetime' },
        yAxes: [{ id: 'p', name: 'Price' }],
        series: [{ name: 'BB', kind: 'arearange', yAxis: 'p', role: 'neutral', data: [[0, 1, 2]] }],
        meta: { stock: true },
      },
      { cdnScripts: true },
    );
    expect(html).toContain('highcharts-more.js');
  });
});

describe('renderChartPage — self-contained HTML', () => {
  it('inlines vendored scripts by default (no CDN dependency)', () => {
    const html = renderChartPage(fixture('revenue_margins'));
    expect(html.startsWith('<!doctype html>')).toBe(true);
    expect(html).toContain('var AK');              // formatter shipped inline
    expect(html).toContain("Highcharts.chart('c'"); // core ctor
    // no external <script src> tags — fully self-contained
    expect(html).not.toMatch(/<script\s[^>]*src="https?:/);
    expect(html).not.toContain('cdn.jsdelivr.net');
    expect(html).not.toContain('__fn__');           // descriptors fully hydrated
    expect(html.length).toBeGreaterThan(100_000);   // inline scripts are present
  });

  it('uses stockChart + inlines highstock for a price chart', () => {
    const html = renderChartPage(fixture('price_candlestick'));
    expect(html).toContain("Highcharts.stockChart('c'");
    expect(html).not.toContain('cdn.jsdelivr.net');
    expect(html.length).toBeGreaterThan(100_000);
  });

  it('inlines highcharts-more for waterfall (larger than a core chart)', () => {
    const htmlCore = renderChartPage(fixture('revenue_margins'));
    const htmlWaterfall = renderChartPage(fixture('waterfall'));
    // waterfall includes highcharts-more.js on top of core — must be meaningfully larger
    expect(htmlWaterfall.length).toBeGreaterThan(htmlCore.length + 50_000);
  });

  it('cdnScripts:true emits lightweight <script src> tags instead of inline', () => {
    const html = renderChartPage(fixture('revenue_margins'), { cdnScripts: true });
    expect(html).toContain('cdn.jsdelivr.net/npm/highcharts@12/highcharts.js');
    expect(html).not.toContain('code.highcharts.com');
    expect(html.length).toBeLessThan(50_000); // no inline payload
  });
});
