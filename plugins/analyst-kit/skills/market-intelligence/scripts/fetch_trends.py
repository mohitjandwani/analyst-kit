"""fetch_trends.py -- raw Google Trends series -> tidy CSV (provenance schema).

Thin CLI over trends_client. The agent uses this for Step-1 keyword
exploration/validation and for ad-hoc pulls.

Examples
--------
    # 12-month weekly series for one keyword, US:
    python fetch_trends.py --keywords "victoria's secret" --date "today 12-m" --geo US

    # up to 5 keywords (each may be a '+' combination) on a shared 0-100 scale:
    python fetch_trends.py --keywords "victoria's secret" "lingerie + victoria's secret" --geo US

    # manual-exploration URLs (Step 1.0): prints Google Trends web links, NO API call:
    python fetch_trends.py --keywords "lingerie + victoria's secret" --explore-urls

Every output row carries the section-2.6 provenance columns:
    bucket_start, keyword, is_partial, fetched_at, geo, date_range, granularity, value
`--keep-partial` is the DEFAULT (is_partial is an explicit column the consumer
can filter on); pass `--drop-partial` to omit in-progress buckets up front.
"""
import argparse
import sys

import trends_client as tc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keywords", nargs="+", required=True,
                   help="Up to 5 keywords (relative mode). Each may be a '+' "
                        "combination, e.g. \"lingerie + victoria's secret\".")
    p.add_argument("--date", default="today 12-m",
                   help="Trends date range. Relative (e.g. 'today 12-m', 'today 5-y') "
                        "or absolute 'YYYY-MM-DD YYYY-MM-DD'. Default: 'today 12-m'.")
    p.add_argument("--geo", default="US", help="Geography (e.g. US). Default: US.")
    p.add_argument("--data-type", default="TIMESERIES",
                   choices=["TIMESERIES", "RELATED_QUERIES"],
                   help="TIMESERIES (default) or RELATED_QUERIES (disambiguation).")
    p.add_argument("--tz", default=None, help="Timezone offset in minutes (optional).")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--keep-partial", dest="drop_partial", action="store_false",
                     help="Keep in-progress (partial) buckets [DEFAULT].")
    grp.add_argument("--drop-partial", dest="drop_partial", action="store_true",
                     help="Omit in-progress (partial) buckets.")
    p.set_defaults(drop_partial=False)
    p.add_argument("--explore-urls", action="store_true",
                   help="Print Google Trends web-UI URLs for the keywords instead "
                        "of calling the API (free manual exploration, Step 1.0).")
    p.add_argument("--no-cache", action="store_true", help="Bypass the disk cache.")
    p.add_argument("--out", default=None, help="Write CSV here instead of stdout.")
    args = p.parse_args(argv)

    if len(args.keywords) > 5:
        p.error("at most 5 keywords per relative request (Google Trends limit).")

    tc.load_dotenv()

    if args.explore_urls:
        # Manual exploration mode -- zero API spend.
        date = args.date if args.date != "today 12-m" else "today 5-y"
        for kw in args.keywords:
            print(tc.explore_url(kw, date=date, geo=args.geo))
        return 0

    # Pack all keywords into ONE comma-joined relative request (shared scale).
    q = ", ".join(args.keywords)
    try:
        rows, granularity, _ = tc.fetch_series(
            q, date=args.date, geo=args.geo, data_type=args.data_type,
            tz=args.tz, drop_partial=args.drop_partial,
            use_cache=not args.no_cache, log=lambda m: print(m, file=sys.stderr),
        )
    except tc.TrendsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    csv_text = tc.rows_to_csv(rows)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(csv_text)
        print(f"Wrote {len(rows)} rows ({granularity}) -> {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(csv_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
