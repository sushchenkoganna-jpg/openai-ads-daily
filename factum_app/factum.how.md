---
sources:
- ref: https://developers.openai.com/ads/reporting
  title: "OpenAI Ads Advertiser API — insights and conversions/insights"
- ref: https://github.com/sushchenkoganna-jpg/openai-ads-daily
  title: "the pipeline (private): pull.py, build_dash.py, GitHub Action"
---
OpenAI Ads (ChatGPT ads) daily dashboard. A GitHub Action pulls the last 7 days from the OpenAI Ads API every day at
09:00 UTC (campaign x day: impressions, clicks, spend, conversions; conversions by country from /conversions/insights,
attribution 30d click / 1d view, account timezone America/Los_Angeles) and commits dashboard/data.json. This app's handler
`data` reads that file through the api.github.com connection (read-only token on that one repository) and caches it 1 h;
the page computes every metric (CTR, CPC, CPA, CVR, deltas vs the previous period) in the browser.
Not here: spend/clicks by country (the API's country segment repeats campaign totals), CAC from DWH.
Checked: API totals equal the manual Ads Manager export to the cent on the 6 campaigns it had (Jul–Nov 2026).
