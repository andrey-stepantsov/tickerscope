#!/usr/bin/env python3
"""
Fetch real, coarse (monthly by default) price history into data.json,
which index.html loads when present. Source: Yahoo Finance via yfinance.

Now bakes OHLC (open/high/low/close) so the widget's candlestick view has
real wicks. Closes are also stored separately for the line views.

Usage:
    python3 fetch_data.py            # monthly (default)
    python3 fetch_data.py --weekly
    python3 fetch_data.py --daily
"""
import json, sys, datetime

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance not installed — run: pip install yfinance")

COMPANIES = {
    "INTC": "INTC", "NVDA": "NVDA", "NOK":  "NOK",
    "MSFT": "MSFT", "TSLA": "TSLA", "GOOGL": "GOOGL", "AMD": "AMD",
}
BENCHES = {"SPX": "^GSPC", "DJIA": "^DJI"}

interval_arg = "m"
if "--weekly" in sys.argv: interval_arg = "w"
if "--daily"  in sys.argv: interval_arg = "d"

YF_INTERVAL = {"m": "1mo", "w": "1wk", "d": "1d"}[interval_arg]
INTERVAL_NAME = {"m": "monthly", "w": "weekly", "d": "daily"}[interval_arg]

def fetch(ticker_sym):
    """Return {date_str: {o,h,l,c}} from Yahoo Finance."""
    t = yf.Ticker(ticker_sym)
    hist = t.history(period="max", interval=YF_INTERVAL, auto_adjust=True)
    if hist.empty:
        return {}
    out = {}
    for ts, row in hist.iterrows():
        # ts is a Timestamp; format as YYYY-MM-DD
        date_str = ts.strftime("%Y-%m-%d")
        try:
            out[date_str] = {
                "o": round(float(row["Open"]),  4),
                "h": round(float(row["High"]),  4),
                "l": round(float(row["Low"]),   4),
                "c": round(float(row["Close"]), 4),
            }
        except (KeyError, ValueError):
            continue
    return out

def main():
    raw = {}
    for label, sym in {**COMPANIES, **BENCHES}.items():
        try:
            s = fetch(sym)
            if len(s) < 2:
                print(f"  ! {label} ({sym}): too few rows, skipping"); continue
            raw[label] = s
            print(f"  ok {label:<6} {sym:<8} {len(s)} bars")
        except Exception as e:
            print(f"  ! {label} ({sym}): {e}")

    if not raw:
        sys.exit("No data fetched — check your network / symbols.")

    lo = max(min(d) for d in raw.values())
    hi = min(max(d) for d in raw.values())
    master = sorted({d for s in raw.values() for d in s if lo <= d <= hi})

    def aligned(s):
        o, h, l, c, last = [], [], [], [], None
        for d in master:
            if d in s: last = s[d]
            if last:
                o.append(round(last["o"], 4)); h.append(round(last["h"], 4))
                l.append(round(last["l"], 4)); c.append(round(last["c"], 4))
            else:
                o.append(None); h.append(None); l.append(None); c.append(None)
        return {"o": o, "h": h, "l": l, "c": c}

    series, ohlc, benches, bench_ohlc = {}, {}, {}, {}
    for label, s in raw.items():
        a = aligned(s)
        if label in COMPANIES:
            series[label] = a["c"]; ohlc[label] = a
        else:
            benches[label] = a["c"]; bench_ohlc[label] = a

    data = {
        "meta": {
            "source": "finance.yahoo.com",
            "interval": INTERVAL_NAME,
            "generated": datetime.datetime.utcnow().isoformat() + "Z",
            "start": master[0], "end": master[-1], "ohlc": True,
        },
        "dates": master,
        "series": series, "ohlc": ohlc,
        "benches": benches, "benchOhlc": bench_ohlc,
    }
    with open("data.json", "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"\nWrote data.json — {len(master)} {data['meta']['interval']} OHLC bars, "
          f"{data['meta']['start']} to {data['meta']['end']}")

if __name__ == "__main__":
    main()
