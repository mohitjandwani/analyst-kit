import { describe, expect, it } from 'vitest';

import { fmtRef, HELPERS_JS } from '../src/format.js';

// Build the exact browser-side helper the page ships and exercise it directly.
const AK = new Function(`${HELPERS_JS}\nreturn AK;`)() as {
  fmt: (v: number | null, o?: Record<string, unknown>) => string;
};

describe('AK.fmt (shipped browser formatter)', () => {
  it('formats scaled money with currency + unit', () => {
    expect(AK.fmt(416.2, { currency: '$', unit: 'B' })).toBe('$416.2B');
  });

  it('uses accounting parentheses for negatives', () => {
    expect(AK.fmt(-2.5, { currency: '$', unit: 'M' })).toBe('($2.5M)');
  });

  it('formats percent', () => {
    expect(AK.fmt(26.915, { percent: true })).toBe('26.9%');
  });

  it('never emits a raw large number — always scaled+unit', () => {
    // 12.312135 (already scaled to M by the data layer) → "$12.3M", not 12312135.
    expect(AK.fmt(12.312135, { currency: '$', unit: 'M' })).toBe('$12.3M');
  });

  it('special-cases zero and null', () => {
    expect(AK.fmt(0, { currency: '$', unit: 'B' })).toBe('$0');
    expect(AK.fmt(null)).toBe('—');
  });

  it('honors fixed decimals (EPS/per-share = 2 dp, even whole values)', () => {
    expect(AK.fmt(1, { currency: '$', decimals: 2 })).toBe('$1.00');
    expect(AK.fmt(-0.45, { currency: '$', decimals: 2 })).toBe('($0.45)');
  });
});

describe('fmtRef', () => {
  it('produces a descriptor and drops undefined keys', () => {
    expect(fmtRef({ currency: '$', unit: 'B' })).toEqual({ __fn__: 'fmt', opts: { currency: '$', unit: 'B' } });
    expect(fmtRef({ percent: true })).toEqual({ __fn__: 'fmt', opts: { percent: true } });
    expect(fmtRef({})).toEqual({ __fn__: 'fmt', opts: {} });
  });
});
