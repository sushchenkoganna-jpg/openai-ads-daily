#!/usr/bin/env python3
"""dashboard/template.html + data/*.csv -> dashboard/index.html (data embedded, no server needed).
Factum serves dashboard/index.html live from this repository, so a commit is all a daily update needs."""
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
MET = ["impressions", "clicks", "spend", "conversions"]


def load(name):
    p = os.path.join(HERE, "data", name)
    if not os.path.exists(p): return []
    with open(p, newline="") as f: return list(csv.DictReader(f))


def n(x):
    v = float(x or 0); return int(v) if v == int(v) else round(v, 2)


def main():
    camp, ctry = load("campaign_daily.csv"), load("country_daily.csv")
    names = sorted({r["campaign"] for r in camp} | {r["campaign"] for r in ctry})
    codes = sorted({r["country"] for r in ctry}); ci = {c: i for i, c in enumerate(names)}; ki = {c: i for i, c in enumerate(codes)}
    meta_p = os.path.join(HERE, "data", "meta.json")
    data = {"meta": json.load(open(meta_p)) if os.path.exists(meta_p) else {},
            "camps": names, "ctry": codes,
            "c": [[r["date"], ci[r["campaign"]]] + [n(r[m]) for m in MET] for r in camp],
            "k": [[r["date"], ci[r["campaign"]], ki[r["country"]]] + [n(r[m]) for m in MET] for r in ctry]}
    tpl = open(os.path.join(HERE, "dashboard", "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    with open(os.path.join(HERE, "dashboard", "index.html"), "w", encoding="utf-8") as f: f.write(html)
    print(f"dashboard: {len(data['c'])} campaign rows, {len(data['k'])} country rows, {len(html) // 1024} KB")


if __name__ == "__main__":
    main()
