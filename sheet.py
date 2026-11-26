#!/usr/bin/env python3
"""Mirror data/*.csv into the Google Sheet GSHEET_ID (tabs campaign_daily, country_daily). Stdlib only.

Token: env GSHEET_TOKEN_JSON (the whole authorized-user JSON with client_id, client_secret, refresh_token)
or the local file ~/Documents/Claude/gsheet_token_spreadsheets.json. Each tab is rewritten whole (2 calls per tab):
idempotent, so a restated day never leaves a stale row.
  python3 sheet.py              # sync
  python3 sheet.py --create     # create the spreadsheet once, print its id
"""
import argparse, csv, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TABS = {"campaign_daily": "data/campaign_daily.csv", "country_daily": "data/country_daily.csv"}
API = "https://sheets.googleapis.com/v4/spreadsheets"


def req(url, body=None, token=None, method=None, form=False):
    data = None; h = {}
    if token: h["Authorization"] = f"Bearer {token}"
    if body is not None:
        if form: data = urllib.parse.urlencode(body).encode()
        else: data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(r, timeout=120) as resp: return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Sheets {e.code}: {e.read().decode()[:400]}")


def access_token():
    raw = os.environ.get("GSHEET_TOKEN_JSON")
    t = json.loads(raw) if raw else json.load(open(os.path.expanduser("~/Documents/Claude/gsheet_token_spreadsheets.json")))
    return req(t.get("token_uri") or "https://oauth2.googleapis.com/token",
               {"client_id": t["client_id"], "client_secret": t["client_secret"], "refresh_token": t["refresh_token"],
                "grant_type": "refresh_token"}, form=True)["access_token"]


def cell(c, v):
    if c in ("date", "campaign_id", "campaign", "country"): return v
    try: return float(v)
    except ValueError: return v


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--create", action="store_true"); a = ap.parse_args()
    tok = access_token()
    if a.create:
        r = req(API, {"properties": {"title": "OpenAI Ads daily"}, "sheets": [{"properties": {"title": t}} for t in TABS]}, tok)
        print(r["spreadsheetId"], r["spreadsheetUrl"]); return
    sid = os.environ.get("GSHEET_ID")
    if not sid: print("GSHEET_ID not set - skip sheet sync", file=sys.stderr); return
    for tab, path in TABS.items():
        with open(os.path.join(HERE, path), newline="") as f:
            rows = list(csv.reader(f))
        hdr = rows[0]; vals = [hdr] + [[cell(c, v) for c, v in zip(hdr, r)] for r in rows[1:]]
        rng = urllib.parse.quote(tab)
        req(f"{API}/{sid}/values/{rng}:clear", {}, tok)
        req(f"{API}/{sid}/values/{rng}!A1?valueInputOption=RAW", {"values": vals}, tok, method="PUT")
        print(f"{tab}: {len(vals) - 1} rows", file=sys.stderr)


if __name__ == "__main__":
    main()
