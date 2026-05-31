# Markets Lab
A zero-dependency static web app comparing seven equities (Intel, Nvidia, Nokia,
Microsoft, Tesla, Google, AMD) against the S&P 500, Dow Jones, and a synthetic
HBM-spot index. Supports line and candlestick views, equal-weight composite
indices, horizon windows (1M–3Y), and indexed / raw / log scales.

- **Live:** https://andrey-stepantsov.github.io/tickerscope/
- **Real data** (Stooq monthly OHLC) is baked into `data.json` by CI; falls
  back to a synthetic GBM sandbox when `data.json` is absent.

## Local development

```
python3 fetch_data.py        # generates data.json (monthly closes + OHLC)
python3 -m http.server       # then open http://localhost:8000
```

Opening `index.html` directly via `file://` works in synthetic mode only;
browsers block `fetch()` of local files, which the widget handles gracefully.

## Deploy

CI handles it. See `.github/workflows/`.
