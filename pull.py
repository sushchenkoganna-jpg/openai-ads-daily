#!/usr/bin/env python3
"""OpenAI Ads -> data/campaign_daily.csv + data/country_daily.csv (stdlib only).

Two API calls per run (campaign x day, campaign x day x country) over the last --days days (default 7: spend and
conversions are restated for a few days). Rows for those days are replaced, older rows are kept.

  OPENAI_ADS_API_KEY=... python3 pull.py               # daily: last 7 complete days
  OPENAI_ADS_API_KEY=... python3 pull.py --since 2026-07-01   # backfill
Env: OPENAI_ADS_TZ overrides the account timezone (else read from GET /v1/ad_account, fallback UTC).
"""
import argparse, csv, datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

API = "https://api.ads.openai.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MET = ["impressions", "clicks", "spend", "conversions"]
CAMP_COLS = ["date", "campaign_id", "campaign"] + MET
CTRY_COLS = ["date", "campaign_id", "campaign", "country"] + MET
ATTR = {"attribution_window_days": "30", "view_through_attribution_window_days": "1"}


def log(*a): print(*a, file=sys.stderr, flush=True)


def call(path, params=None, key=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for i in range(5):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "openai-ads-daily/1.0 (+curl compatible)"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:8000]
            if e.code in (429, 500, 502, 503, 504) and i < 4:
                wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** i
                log(f"HTTP {e.code}, retry in {wait}s"); time.sleep(wait); continue
            raise SystemExit(f"OpenAI Ads API {e.code} on {path}: {body}")
        except urllib.error.URLError as e:
            if i < 4: time.sleep(5 * 2 ** i); continue
            raise


def rows_of(resp):
    for k in ("data", "rows", "results", "insights"):
        if isinstance(resp.get(k), list): return resp[k]
    return []


def insights(key, since, until, tz, segment=None):
    """All rows for [since, until] (inclusive), following pagination."""
    pre = f"{segment}." if segment else ""
    params = {"aggregation_level": "campaign", "time_granularity": "daily",
              "time_ranges[]": json.dumps({"type": "date_range", "since": since, "until": until, "timezone": tz}),
              "fields[]": ["campaign_id", "campaign_name", "readable_time"] + [pre + m for m in MET], **ATTR}
    if segment: params["segments[]"] = segment
    out, page = [], 0
    while True:
        resp = call("/ad_account/insights", params, key)
        rows = rows_of(resp); out += rows; page += 1
        cur = resp.get("next_cursor") or resp.get("after") or (resp.get("paging") or {}).get("after") or resp.get("last_id")
        if not rows or not resp.get("has_more") or not cur or page > 200: break
        params["after"] = cur
    if out: log(f"{segment or 'campaign'}: {len(out)} rows, keys {sorted(out[0])}")
    return out


def val(r, name, seg=None):
    for k in ([f"{seg}.{name}"] if seg else []) + [name]:
        if k in r and r[k] is not None:
            v = r[k]
            return v.get("value", v.get("amount")) if isinstance(v, dict) else v
    if isinstance(r.get(seg), dict): return r[seg].get(name)
    return None


def num(x):
    try: return round(float(x), 4)
    except (TypeError, ValueError): return 0.0


def norm(rows, seg=None):
    out = []
    for r in rows:
        d = str(val(r, "readable_time") or val(r, "date") or "")[:10]
        if not d: continue
        o = {"date": d, "campaign_id": str(val(r, "campaign_id") or ""), "campaign": val(r, "campaign_name") or ""}
        if seg:
            c = r.get(seg)
            o["country"] = (c.get("code") or c.get("country") or c.get("name")) if isinstance(c, dict) else (
                c or val(r, "country", seg) or val(r, "code", seg) or "??")
        for m in MET: o[m] = num(val(r, m, seg))
        out.append(o)
    return out


def upsert(path, cols, new, since, until):
    old = []
    if os.path.exists(path):
        with open(path, newline="") as f: old = [r for r in csv.DictReader(f) if not (since <= r["date"] <= until)]
    rows = old + [{c: r.get(c, "") for c in cols} for r in new]
    rows = [r for r in rows if any(num(r[m]) for m in MET)]          # zero rows add nothing to sums
    rows.sort(key=lambda r: tuple(str(r[c]) for c in cols[:4]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since"); ap.add_argument("--until"); ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    key = os.environ.get("OPENAI_ADS_API_KEY") or open(os.path.expanduser("~/.config/openai_ads/key")).read().strip()
    tz = os.environ.get("OPENAI_ADS_TZ")
    if not tz:
        acc = call("/ad_account", key=key)
        tz = acc.get("timezone") or acc.get("time_zone") or acc.get("reporting_timezone") or "UTC"
    today = dt.datetime.now(ZoneInfo(tz)).date()
    until = a.until or str(today - dt.timedelta(days=1))
    since = a.since or str(today - dt.timedelta(days=a.days))
    log(f"tz {tz}, {since}..{until}")
    os.makedirs(DATA, exist_ok=True)
    # non-hourly ranges are limited to 365 days per request
    s = dt.date.fromisoformat(since); u = dt.date.fromisoformat(until); camp, ctry = [], []
    while s <= u:
        e = min(u, s + dt.timedelta(days=364))
        camp += norm(insights(key, str(s), str(e), tz))
        ctry += norm(insights(key, str(s), str(e), tz, "country"), "country")
        s = e + dt.timedelta(days=1)
    n1 = upsert(os.path.join(DATA, "campaign_daily.csv"), CAMP_COLS, camp, since, until)
    n2 = upsert(os.path.join(DATA, "country_daily.csv"), CTRY_COLS, ctry, since, until)
    with open(os.path.join(DATA, "meta.json"), "w") as f:
        json.dump({"pulled_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "timezone": tz,
                   "last_day": until, "attribution": "30d click / 1d view, ad event time"}, f)
    log(f"campaign_daily {n1} rows, country_daily {n2} rows")


if __name__ == "__main__":
    main()
