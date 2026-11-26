# OpenAI Ads daily

Daily OpenAI Ads (ChatGPT ads) export → CSV in this repo → Google Sheet → Factum dashboard.
Runs in GitHub Actions: no local machine, no Claude (zero tokens), 2 API calls a day.

```
GitHub Actions 04:30 UTC
  pull.py        GET /v1/ad_account/insights (campaign × day); conversions by country (/conversions/insights);
                 the last 7 days are rewritten (conversions mature)
  build_dash.py  data/*.csv → dashboard/data.json + dashboard/index.html
  sheet.py       data/*.csv → Google Sheet (tabs campaign_daily, country_daily)
  commit         Factum app polar-crest-j8 reads dashboard/data.json via the GitHub API (cached 1 h)
```

## Setup (once)
| What | Where |
|---|---|
| `OPENAI_ADS_API_KEY` (secret) | ads.openai.com → Settings → API keys; repo Settings → Secrets and variables → Actions |
| `GSHEET_TOKEN_JSON` (secret) | contents of `gsheet_token_spreadsheets.json` (authorized user, spreadsheets scope) |
| `GSHEET_ID` (variable) | id of the "OpenAI Ads daily" sheet (`python3 sheet.py --create`) |
| `OPENAI_ADS_TZ` (variable, optional) | account timezone if `GET /v1/ad_account` does not return it |
| Factum GitHub key | fine-grained PAT, this repo only, Contents: Read-only → `pbpaste \| factum app secret polar-crest-j8 api.github.com --connection` (expires in 1 year) |

Backfill: Actions → OpenAI Ads daily → Run workflow → `since` = `2026-07-01`.
Page change: edit `dashboard/template.html`, `cp dashboard/template.html factum_app/index.html`,
`factum publish factum_app --update polar-crest-j8 --how factum_app/factum.how.md` (company network).

## Metrics
Spend, Impressions, Clicks, CTR, CPC, Conversions (trials, 30d click / 1d view), CPA, CVR — by day, campaign,
type (Forms / Functions, from the campaign name) and conversions by country; each vs the previous period.
The last 2 days are incomplete: OpenAI keeps attributing conversions.

## Limits
- Spend and clicks by country are not available (the API's country segment repeats campaign totals).
- No CAC from the DWH (reachable only from the company network).
- Keys belong to people (OpenAI API key, Google OAuth, GitHub PAT): replace them if the owner leaves.
- A failed run → GitHub emails the repo owner.
