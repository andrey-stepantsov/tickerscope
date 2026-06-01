#!/usr/bin/env python3
"""
Fetch real price history into data.json.
Source: Yahoo Finance via yfinance.

Bakes TWO resolutions so the widget can pick the right one per horizon:
  daily  — last 6 months of 1-day bars  (for 1M and 3M views)
  weekly — full history of 1-week bars  (for 6M, 1Y, 2Y, 3Y, Max views)

Each resolution has its own dates / series / ohlc / benches / benchOhlc.
Top-level meta reflects the weekly dataset (widest range).

Usage:
    python3 fetch_data.py
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

def fetch(ticker_sym, yf_interval, period, start=None):
    """Return {date_str: {o,h,l,c}} from Yahoo Finance."""
    t = yf.Ticker(ticker_sym)
    if start:
        hist = t.history(start=start, interval=yf_interval, auto_adjust=True)
    else:
        hist = t.history(period=period, interval=yf_interval, auto_adjust=True)
    if hist.empty:
        return {}
    out = {}
    for ts, row in hist.iterrows():
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

def build_dataset(yf_interval, period, label):
    """Fetch all symbols at one resolution; return aligned dataset dict."""
    raw = {}
    for lbl, sym in {**COMPANIES, **BENCHES}.items():
        try:
            s = fetch(sym, yf_interval, period, start=("1990-01-01" if yf_interval=="1wk" else None))
            if len(s) < 2:
                print(f"  ! {lbl} ({sym}): too few rows, skipping"); continue
            raw[lbl] = s
            print(f"  ok {lbl:<6} {sym:<8} {len(s)} {label} bars")
        except Exception as e:
            print(f"  ! {lbl} ({sym}): {e}")

    if not raw:
        return None

    # Use the EARLIEST start of any symbol and LATEST common end.
    # Symbols with later starts will forward-fill from their first available bar.
    lo = min(min(d) for d in raw.values())
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
    for lbl, s in raw.items():
        a = aligned(s)
        if lbl in COMPANIES:
            series[lbl] = a["c"]; ohlc[lbl] = a
        else:
            benches[lbl] = a["c"]; bench_ohlc[lbl] = a

    return {
        "dates": master, "start": master[0], "end": master[-1],
        "series": series, "ohlc": ohlc,
        "benches": benches, "benchOhlc": bench_ohlc,
    }

def main():
    print("Fetching weekly (full history)…")
    weekly = build_dataset("1wk", "max", "weekly")
    if not weekly:
        sys.exit("Weekly fetch failed entirely.")

    print("\nFetching daily (last 6 months)…")
    daily = build_dataset("1d", "6mo", "daily")
    if not daily:
        print("  Warning: daily fetch failed — widget will use weekly for all horizons.")
        daily = None

    data = {
        "meta": {
            "source": "finance.yahoo.com",
            "interval": "dual",          # signals new format to index.html
            "generated": datetime.datetime.utcnow().isoformat() + "Z",
            "start": weekly["start"], "end": weekly["end"], "ohlc": True,
        },
        # Top-level keys kept for backward compat (validReal check in index.html)
        "dates":     weekly["dates"],
        "series":    weekly["series"],
        "ohlc":      weekly["ohlc"],
        "benches":   weekly["benches"],
        "benchOhlc": weekly["benchOhlc"],
        # New dual-resolution sub-objects
        "weekly": {k: weekly[k] for k in ("dates","series","ohlc","benches","benchOhlc")},
        "daily":  ({k: daily[k]  for k in ("dates","series","ohlc","benches","benchOhlc")}
                   if daily else None),
    }

    with open("data.json", "w") as f:
        json.dump(data, f, separators=(",", ":"))

    w_bars = len(weekly["dates"])
    d_bars = len(daily["dates"]) if daily else 0
    print(f"\nWrote data.json — weekly: {w_bars} bars ({weekly['start']} → {weekly['end']})"
          + (f", daily: {d_bars} bars ({daily['start']} → {daily['end']})" if daily else ""))

if __name__ == "__main__":
    main()
