import { describe, expect, it } from 'vitest';

import { optionsToJs, renderChartPage, scriptsFor } from '../src/render.js';
import { fixture } from './helpers.js';

describe('optionsToJs', () => {
  it('hydrates a formatter descriptor into a real function', () => {
    const js = optionsToJs({ formatter: { __fn__: 'fmt', opts: { currency: '$', unit: 'B' } } });
    expect(js).toContain('function()');
    expect(js).toContain('HFA.fmt');
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
});

describe('renderChartPage — self-contained HTML', () => {
  it('embeds the helper + a Highcharts.chart call, no leftover descriptors', () => {
    const html = renderChartPage(fixture('revenue_margins'));
    expect(html.startsWith('<!doctype html>')).toBe(true);
    expect(html).toContain('var HFA');                 // formatter shipped inline
    expect(html).toContain("Highcharts.chart('c'");    // core ctor
    expect(html).toContain('cdn.jsdelivr.net/npm/highcharts@12/highcharts.js');
    expect(html).not.toContain('__fn__');              // descriptors fully hydrated
  });

  it('uses stockChart + highstock for a price chart', () => {
    const html = renderChartPage(fixture('price_candlestick'));
    expect(html).toContain("Highcharts.stockChart('c'");
    expect(html).toContain('/highstock.js');
  });

  it('loads highcharts-more for the waterfall page (waterfall is not in core)', () => {
    const html = renderChartPage(fixture('waterfall'));
    expect(html).toContain('highcharts-more.js');
  });
});
