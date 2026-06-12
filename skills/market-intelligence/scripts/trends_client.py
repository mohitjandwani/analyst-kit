"""Shared SerpAPI Google Trends client for the market-intelligence skill.

Single source of truth for: auth, the authenticated HTTP call, a *mandatory*
disk cache (free tier = 100 searches/month, so every avoidable call must be a
cache hit), parsing the response into the provenance schema of the plan's
section 2.6, and asserting the returned granularity.

Stdlib only (urllib) -- no third-party dependencies. All credentials come from
the SERPAPI_API_KEY environment variable; the key is never hardcoded or logged.

Provenance schema (every row, every output -- plan section 2.6):
    bucket_start  -- parsed from the Unix `timestamp` (NEVER the `date` string)
    keyword       -- the verbatim `q` term (e.g. "lingerie + victoria's secret")
    value         -- `extracted_value` (int)
    is_partial    -- point-level `partial_data` flag, always explicit True/False
    fetched_at    -- UTC datetime the live API call was made; survives cache hits
    geo, date_range, granularity -- request context needed to reproduce the scale
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE_URL = "https://serpapi.com/search.json"

# Granularity is inferred from the gap (seconds) between consecutive bucket
# timestamps -- the only reliable signal (plan section 2.3).
SECONDS = {3600: "hourly", 86400: "daily", 604800: "weekly"}
MONTHLY_MIN = 27 * 86400  # ~28-31 days; monthly buckets are uneven, so use a floor

# A response is "fresh forever" only if its window has fully closed (no partial
# bucket) and the request was an absolute date window. Anything containing a
# partial bucket, or a relative range like "today 3-m", must re-expire.
RELATIVE_HINTS = ("now ", "today ", "all")
CACHE_TTL_SECONDS = 6 * 3600  # 6h for mutable (partial / relative) responses


class TrendsError(Exception):
    """Raised on a non-retryable SerpAPI / Google Trends failure."""


def get_api_key():
    key = os.environ.get("SERPAPI_API_KEY")
    if not key:
        raise TrendsError(
            "SERPAPI_API_KEY not set. Run: export SERPAPI_API_KEY='your_key' "
            "(free key from https://serpapi.com/, 100 searches/month)."
        )
    return key


def load_dotenv(path=None):
    """Best-effort load of a repo-root .env so scripts work without manual export.

    Only fills variables that are not already in the environment. Never prints
    or logs values. Silently does nothing if no .env is found.
    """
    if path is None:
        # walk up from this file looking for a .env (repo root holds the real one)
        here = os.path.abspath(os.path.dirname(__file__))
        for _ in range(8):
            cand = os.path.join(here, ".env")
            if os.path.isfile(cand):
                path = cand
                break
            parent = os.path.dirname(here)
            if parent == here:
                break
            here = parent
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ and v:
                    os.environ[k] = v
    except OSError:
        pass


def default_cache_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")


def _cache_key(params):
    """Stable hash over the quota-relevant request params (key excluded)."""
    relevant = {k: params[k] for k in ("q", "date", "geo", "data_type", "tz") if params.get(k)}
    blob = json.dumps(relevant, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:20]


def _now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _has_partial(raw):
    for pt in raw.get("interest_over_time", {}).get("timeline_data", []) or []:
        if pt.get("partial_data"):
            return True
    return False


def _is_relative(date_range):
    if not date_range:
        return True  # default (no date) is a relative "past 12 months"
    low = date_range.lower()
    return any(low.startswith(h) or low == h.strip() for h in RELATIVE_HINTS)


def _cache_expired(envelope):
    """A cached envelope is fresh forever if its window is closed (absolute range,
    no partial bucket); otherwise it expires after CACHE_TTL_SECONDS."""
    params = envelope.get("request_params", {})
    raw = envelope.get("raw_response", {})
    if _is_relative(params.get("date")) or _has_partial(raw):
        try:
            fetched = datetime.strptime(envelope["fetched_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except (KeyError, ValueError):
            return True
        age = (datetime.now(timezone.utc) - fetched).total_seconds()
        return age > CACHE_TTL_SECONDS
    return False


def _http_get(params, timeout=60, max_retries=3):
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    backoff = 4
    last_err = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
            return json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8"))
            except Exception:
                payload = {}
            # 4xx other than rate-limit are not retryable
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                last_err = e
                continue
            msg = payload.get("error") or f"HTTP {e.code}"
            raise TrendsError(f"SerpAPI error: {msg}")
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
    raise TrendsError(f"SerpAPI request failed after {max_retries} attempts: {last_err}")


def fetch_raw(q, date=None, geo=None, data_type="TIMESERIES", tz=None,
              cache_dir=None, use_cache=True, log=print):
    """Return the envelope {fetched_at, request_params, raw_response}.

    Cache hits preserve the ORIGINAL fetched_at (staleness stays visible).
    Prints whether each fetch was a CACHE HIT or a LIVE call so the user can
    track the 100/month quota.
    """
    cache_dir = cache_dir or default_cache_dir()
    params = {"engine": "google_trends", "q": q, "data_type": data_type}
    if date:
        params["date"] = date
    if geo:
        params["geo"] = geo
    if tz is not None:
        params["tz"] = str(tz)

    os.makedirs(cache_dir, exist_ok=True)
    key = _cache_key(params)
    cache_path = os.path.join(cache_dir, f"{key}.json")

    if use_cache and os.path.isfile(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as fh:
                envelope = json.load(fh)
        except (ValueError, OSError):
            envelope = None
        if envelope and not _cache_expired(envelope):
            if log:
                log(f"  [CACHE HIT] q={q!r} date={date!r} geo={geo!r} "
                    f"(fetched_at={envelope.get('fetched_at')})")
            return envelope
        elif log and envelope:
            log(f"  [CACHE STALE -> refetch] q={q!r} date={date!r}")

    # Live call -- costs one of the 100 monthly searches.
    call_params = dict(params)
    call_params["api_key"] = get_api_key()
    if log:
        log(f"  [LIVE CALL] q={q!r} date={date!r} geo={geo!r} data_type={data_type}")
    raw = _http_get(call_params)

    if isinstance(raw, dict) and raw.get("error"):
        raise TrendsError(f"SerpAPI error: {raw['error']}")

    envelope = {
        "fetched_at": _now_utc_iso(),
        "request_params": params,  # NB: api_key intentionally excluded
        "raw_response": raw,
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return envelope


def assert_granularity(rows, expected=None):
    """Infer granularity from consecutive bucket_start deltas; fail loudly on a
    mismatch with `expected` (guards the ~269-day daily->weekly cliff, 2.3)."""
    if len(rows) < 2:
        return expected
    starts = sorted(r["bucket_start_ts"] for r in rows)
    deltas = [b - a for a, b in zip(starts, starts[1:]) if b > a]
    if not deltas:
        return expected
    gap = min(deltas)  # the smallest gap is the native bucket size
    inferred = SECONDS.get(gap)
    if inferred is None:
        inferred = "monthly" if gap >= MONTHLY_MIN else f"unknown({gap}s)"
    if expected and inferred != expected:
        raise TrendsError(
            f"Granularity mismatch: expected {expected!r} but the response is "
            f"{inferred!r} (consecutive-timestamp gap = {gap}s). Google likely "
            f"down-sampled the requested window -- never request a custom daily "
            f"window longer than 224 days."
        )
    return inferred


def parse_rows(envelope, drop_partial=False):
    """Flatten the envelope into provenance rows (plan section 2.6).

    One row per (timeline point, keyword/value). `keyword` is the verbatim `q`
    series label as returned by Google; `is_partial` is the point-level flag.
    Returns (rows, granularity). Raises on the SerpAPI error / empty-series shapes.
    """
    params = envelope["request_params"]
    raw = envelope["raw_response"]
    fetched_at = envelope["fetched_at"]
    geo = params.get("geo", "")
    date_range = params.get("date", "")

    if isinstance(raw, dict) and raw.get("error"):
        raise TrendsError(f"SerpAPI error: {raw['error']}")

    iot = raw.get("interest_over_time")
    if not iot or not iot.get("timeline_data"):
        raise TrendsError(
            f"Empty interest_over_time for q={params.get('q')!r} -- the keyword "
            f"likely has too little search volume or is unknown to Google Trends."
        )

    rows = []
    for pt in iot["timeline_data"]:
        ts = int(pt["timestamp"])  # Unix seconds, UTC, START of the bucket
        bucket_start = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        is_partial = bool(pt.get("partial_data", False))  # point-level, NOT in values[]
        if drop_partial and is_partial:
            continue
        for v in pt.get("values", []):
            rows.append({
                "bucket_start": bucket_start,
                "bucket_start_ts": ts,
                "keyword": v.get("query", ""),
                "value": int(v.get("extracted_value", 0)),
                "is_partial": is_partial,
                "fetched_at": fetched_at,
                "geo": geo,
                "date_range": date_range,
                # granularity filled in by the caller after assert_granularity
            })
    granularity = assert_granularity(rows)
    for r in rows:
        r["granularity"] = granularity
    return rows, granularity


def fetch_series(q, date=None, geo=None, data_type="TIMESERIES", tz=None,
                 expect_granularity=None, drop_partial=False, cache_dir=None,
                 use_cache=True, log=print):
    """High-level: fetch (cached) + parse + assert granularity. Returns
    (rows, granularity, fetched_at)."""
    envelope = fetch_raw(q, date=date, geo=geo, data_type=data_type, tz=tz,
                         cache_dir=cache_dir, use_cache=use_cache, log=log)
    rows, granularity = parse_rows(envelope, drop_partial=drop_partial)
    if expect_granularity:
        assert_granularity(rows, expected=expect_granularity)
    return rows, granularity, envelope["fetched_at"]


# --- Google Trends web-UI URL builder (manual exploration, zero quota) -------

TRENDS_EXPLORE = "https://trends.google.com/trends/explore"


def explore_url(keyword, date="today 5-y", geo="US"):
    """Build a ready-to-open Google Trends web-UI URL for `keyword`.

    Uses the SAME q/+/quote/- syntax as the API, so a `+` combination keyword
    like "lingerie + victoria's secret" maps to one union series in the UI.
    Free + unlimited -- this powers the manual exploration mode (Step 1.0).
    """
    params = {"date": date, "q": keyword}
    if geo:
        params["geo"] = geo
    # Encode with quote() (no safe chars): spaces -> %20 and the '+' union
    # operator -> %2B. This matters: a *literal* '+' in a URL query is decoded
    # to a SPACE by browsers, which would silently destroy the union operator;
    # %2B survives decoding so Google Trends sees the '+' and unions the terms.
    parts = []
    for k, val in params.items():
        parts.append(f"{k}=" + urllib.parse.quote(str(val), safe=""))
    return TRENDS_EXPLORE + "?" + "&".join(parts)


CSV_COLUMNS = ["bucket_start", "keyword", "value", "is_partial",
               "fetched_at", "geo", "date_range", "granularity"]


def rows_to_csv(rows):
    """Serialize provenance rows to a CSV string (section 2.6 columns, in order)."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow([r.get(c, "") for c in CSV_COLUMNS])
    return buf.getvalue()


if __name__ == "__main__":  # tiny smoke entry; real CLIs live in the sibling files
    load_dotenv()
    try:
        get_api_key()
        print("SERPAPI_API_KEY is set; cache dir:", default_cache_dir())
    except TrendsError as e:
        print(e, file=sys.stderr)
        sys.exit(1)
