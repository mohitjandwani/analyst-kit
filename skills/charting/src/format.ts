/**
 * Number formatting for axis ticks and data labels.
 *
 * The actual formatter runs *in the browser* inside the self-contained page, so it
 * ships as a source string (`HELPERS_JS`) rather than an imported function — this
 * keeps it the single source of truth, testable via `new Function(HELPERS_JS)`.
 * `fmtRef` produces a serializable descriptor that `optionsToJs` (render.ts) turns
 * into a real `function(){…}` referencing `AK.fmt`.
 *
 * Rules baked in: data arrives already scaled, so a label only appends the unit +
 * currency; negatives use accounting parentheses `($2.5M)`; never a raw 12312135.
 */

export interface FmtOpts {
  currency?: string;
  unit?: string;      // 'B' | 'M' | 'K' | ''
  percent?: boolean;
  decimals?: number;
}

/** Browser-side helper, embedded verbatim into every rendered page. */
export const HELPERS_JS = `
var AK = {
  fmt: function (value, opts) {
    opts = opts || {};
    if (value === null || value === undefined || (typeof value === 'number' && isNaN(value))) return '—';
    if (opts.percent) {
      var dp = (opts.decimals == null) ? 1 : opts.decimals;
      return value.toFixed(dp) + '%';
    }
    var dp2 = (opts.decimals == null) ? (opts.unit ? 1 : 0) : opts.decimals;
    var cur = opts.currency || '';
    var unit = opts.unit || '';
    if (value === 0) return cur + '0';
    var body = cur + Math.abs(value).toFixed(dp2) + unit;
    return (value < 0) ? '(' + body + ')' : body;
  }
};
`;

/** A serializable formatter descriptor (hydrated to a JS function by optionsToJs). */
export function fmtRef(opts: FmtOpts): { __fn__: 'fmt'; opts: FmtOpts } {
  // Drop undefined keys so the emitted JSON stays clean.
  const clean: FmtOpts = {};
  if (opts.currency) clean.currency = opts.currency;
  if (opts.unit) clean.unit = opts.unit;
  if (opts.percent) clean.percent = true;
  if (opts.decimals != null) clean.decimals = opts.decimals;
  return { __fn__: 'fmt', opts: clean };
}
