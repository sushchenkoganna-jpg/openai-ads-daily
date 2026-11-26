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


def call(path, params=None, key=None, body=None):
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    h = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "openai-ads-daily/1.0"}
    data = None
    if body is not None: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    for i in range(5):
        req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")[:8000]
            if e.code in (429, 500, 502, 503, 504) and i < 4:
                wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** i
                log(f"HTTP {e.code}, retry in {wait}s"); time.sleep(wait); continue
            if e.code == 413: raise TooBig()
            raise SystemExit(f"OpenAI Ads API {e.code} on {path}: {txt}")
        except urllib.error.URLError:
            if i < 4: time.sleep(5 * 2 ** i); continue
            raise


class TooBig(Exception): pass


def rows_of(resp):
    for k in ("data", "rows", "results", "insights"):
        if isinstance(resp.get(k), list): return resp[k]
    return []


def get(r, *paths):
    """First non-empty value among dotted paths, flat ("a.b") or nested ({"a": {"b"}})."""
    for p in [x for q in paths for x in (q, q.replace(".", "_"))]:
        if p in r and r[p] not in (None, ""): v = r[p]
        else:
            v = r
            for part in p.split("."):
                v = v.get(part) if isinstance(v, dict) else None
            if v in (None, ""): continue
        return v.get("value", v.get("amount")) if isinstance(v, dict) else v
    return None


def sample(tag, rows):
    if rows: log(f"{tag}: {len(rows)} rows; first: {json.dumps({k: v for k, v in rows[0].items() if k != 'id'})[:900]}")


def paged(path, params, key):
    out, page = [], 0
    while True:
        resp = call(path, params, key)
        rows = rows_of(resp); out += rows; page += 1
        cur = resp.get("next_cursor") or resp.get("after") or (resp.get("paging") or {}).get("after") or resp.get("last_id")
        if not rows or not resp.get("has_more") or not cur or page > 200: break
        params["after"] = cur
    return out


def tr(since, until, tz):
    return json.dumps({"type": "date_range", "since": since, "until": until, "timezone": tz})


def campaign_daily(key, since, until, tz):
    rows = paged("/ad_account/insights", {"aggregation_level": "campaign", "time_granularity": "daily",
                 "time_ranges[]": tr(since, until, tz), **ATTR,
                 "fields[]": ["campaign_id", "campaign_name", "readable_time"] + MET}, key)
    sample("campaign", rows)
    return [{"date": str(get(r, "readable_time"))[:10], "campaign_id": str(get(r, "campaign_id") or ""),
             "campaign": get(r, "campaign_name") or "", **{m: num(get(r, m)) for m in MET}} for r in rows]


def country_delivery(key, since, until, tz):
    """Segmented report: delivery only (no conversions), entity-prefixed fields."""
    rows = paged("/ad_account/insights", {"aggregation_level": "campaign", "time_granularity": "daily",
                 "time_ranges[]": tr(since, until, tz), "segments[]": "country", **ATTR,
                 "fields[]": ["campaign.id", "campaign.name", "metadata.readable_time", "country.name",
                              "campaign.impressions", "campaign.clicks", "campaign.spend"]}, key)
    sample("country", rows)
    return [{"date": str(get(r, "metadata.readable_time", "readable_time"))[:10],
             "campaign_id": str(get(r, "campaign.id", "campaign_id") or ""), "campaign": get(r, "campaign.name", "campaign_name") or "",
             "country": get(r, "country.name", "country.code", "country") or "??",
             **{m: num(get(r, f"campaign.{m}", f"country.{m}", m)) for m in ("impressions", "clicks", "spend")}} for r in rows]


def country_conversions(key, since, until, tz, ids):
    """POST /conversions/insights, breakdown=country, 2000-row cap per response -> split dates on 413."""
    z = ZoneInfo(tz)
    ts = lambda d: str(int(dt.datetime.combine(d, dt.time(), z).timestamp()))
    s, u, out = dt.date.fromisoformat(since), dt.date.fromisoformat(until), []
    step = 31
    while s <= u:
        e = min(u, s + dt.timedelta(days=step - 1))
        body = {"aggregation_level": "campaign", "time_granularity": "daily", "entity_ids": ids, "breakdown": "country",
                "time_ranges": [json.dumps({"type": "unix_range", "start": ts(s), "end": ts(e + dt.timedelta(days=1))})],
                **{k: int(v) for k, v in ATTR.items()}}
        try: rows = rows_of(call("/conversions/insights", key=key, body=body))
        except TooBig:
            if step == 1: raise SystemExit("conversions/insights: >2000 rows for one day")
            step = max(1, step // 2); continue
        sample("country conv", rows); out += rows; s = e + dt.timedelta(days=1)
    res = []
    for r in out:
        t = get(r, "readable_time", "metadata.readable_time", "date", "start_time", "time_range.start")
        if isinstance(t, (int, float)) or (isinstance(t, str) and t.isdigit()):
            t = dt.datetime.fromtimestamp(int(t), z).date().isoformat()
        res.append({"date": str(t)[:10], "campaign_id": str(get(r, "campaign_id", "campaign.id", "entity_id", "id") or ""),
                    "country": get(r, "country.name", "country", "breakdown.country", "breakdown_value", "country.code") or "??",
                    "conversions": num(get(r, "conversions"))})
    return res


def num(x):
    try: return round(float(x), 4)
    except (TypeError, ValueError): return 0.0


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
    while s <= u:                                  # non-hourly ranges: <= 365 days per request
        e = min(u, s + dt.timedelta(days=364))
        c = campaign_daily(key, str(s), str(e), tz); camp += c
        dl = country_delivery(key, str(s), str(e), tz)
        ids = sorted({r["campaign_id"] for r in c if r["campaign_id"]})
        cv = country_conversions(key, str(s), str(e), tz, ids) if ids else []
        names = {r["campaign_id"]: r["campaign"] for r in c}
        g = {}
        for r in dl + [dict(x, impressions=0, clicks=0, spend=0) for x in cv]:
            k = (r["date"], r["campaign_id"], r["country"])
            o = g.setdefault(k, {"date": k[0], "campaign_id": k[1], "country": k[2], "campaign": names.get(k[1], r.get("campaign", "")),
                                 **{m: 0.0 for m in MET}})
            for m in MET: o[m] += r.get(m, 0)
        ctry += g.values()
        s = e + dt.timedelta(days=1)
    n1 = upsert(os.path.join(DATA, "campaign_daily.csv"), CAMP_COLS, camp, since, until)
    n2 = upsert(os.path.join(DATA, "country_daily.csv"), CTRY_COLS, ctry, since, until)
    with open(os.path.join(DATA, "meta.json"), "w") as f:
        json.dump({"pulled_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "timezone": tz,
                   "last_day": until, "attribution": "30d click / 1d view, ad event time"}, f)
    log(f"campaign_daily {n1} rows, country_daily {n2} rows")


if __name__ == "__main__":
    main()
