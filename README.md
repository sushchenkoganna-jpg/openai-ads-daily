# OpenAI Ads daily

Щоденне вивантаження OpenAI Ads (ChatGPT ads) → CSV у цьому репо → Google Таблиця → борда у Factum.
Працює в GitHub Actions, без локального Mac і без Claude (0 токенів), 2 запити до API на день.

```
GitHub Actions 04:30 UTC
  pull.py        GET /v1/ad_account/insights: campaign × day, campaign × day × country; останні 7 днів перезаписуються
  build_dash.py  data/*.csv → dashboard/index.html (дані вбудовані в сторінку)
  sheet.py       data/*.csv → Google Таблиця (вкладки campaign_daily, country_daily)
  commit         Factum віддає dashboard/index.html з репо live
```

## Налаштування (один раз)
| Що | Де |
|---|---|
| `OPENAI_ADS_API_KEY` (secret) | ads.openai.com → Settings → API keys → Create; Settings → Secrets and variables → Actions |
| `GSHEET_TOKEN_JSON` (secret) | вміст `gsheet_token_spreadsheets.json` (authorized user, scope spreadsheets) |
| `GSHEET_ID` (variable) | id таблиці «OpenAI Ads daily» (`python3 sheet.py --create`) |
| `OPENAI_ADS_TZ` (variable, необов’язково) | таймзона акаунта, якщо `GET /v1/ad_account` її не повертає |

Backfill: Actions → OpenAI Ads daily → Run workflow → `since` = `2026-07-01`.

Factum (з VPN, один раз): `factum github new sushchenkoganna-jpg/openai-ads-daily dashboard/index.html`
(Factum GitHub App має бачити репо: `factum github repos`).

## Метрики
Spend, Impressions, Clicks, CTR, CPC, Conversions (тріали, атрибуція 30d click / 1d view), CPA, CVR; по днях,
кампаніях, країнах; порівняння з попереднім періодом. Останні 2 дні неповні — OpenAI дораховує конверсії.

## Обмеження
- Токени належать людям (API-ключ OpenAI, Google OAuth). Якщо власник іде — замінити секрети й передати репо.
- CAC з DWH не рахується (DWH доступний лише з корпоративної мережі).
- Помилка запуску → GitHub надсилає email власнику репо.
