#!/usr/bin/env python3
"""
Fetch real price history into data.json directly via Yahoo Finance v8 API.
No third-party dependencies — uses only urllib from the standard library.

Bakes TWO resolutions:
  daily  — last 12 months of 1-day bars  (for 1M, 3M, 6M views)
  weekly — full history of 1-week bars   (for 1Y, 3Y, Max views)

Usage:
    python3 fetch_data.py
"""
import json, sys, datetime, time
import urllib.request, urllib.error

COMPANIES = {
    "INTC": "INTC", "NVDA": "NVDA", "NOK":  "NOK",
    "MSFT": "MSFT", "TSLA": "TSLA", "GOOGL": "GOOGL", "AMD": "AMD",
}
BENCHES = {"SPX": "^GSPC", "DJIA": "^DJI"}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch(sym, interval, range_or_start):
    """
    Call Yahoo Finance v8 chart API.
    range_or_start: a range string like '1y' or a start date string 'YYYY-MM-DD'.
    Returns {date_str: {o,h,l,c}}.
    """
    if range_or_start[0].isdigit():          # it's a date string
        start_ts = int(datetime.datetime.strptime(range_or_start, "%Y-%m-%d").timestamp())
        end_ts   = int(datetime.datetime.utcnow().timestamp()) + 86400
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
               f"?interval={interval}&period1={start_ts}&period2={end_ts}")
    else:                                    # it's a range string like '1y'
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
               f"?interval={interval}&range={range_or_start}")

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}") from e

    result = d.get("chart", {}).get("result")
    if not result:
        raise RuntimeError("empty result")

    result   = result[0]
    tss      = result.get("timestamp", [])
    quotes   = result["indicators"]["quote"][0]
    opens    = quotes.get("open",  [])
    highs    = quotes.get("high",  [])
    lows     = quotes.get("low",   [])
    closes   = quotes.get("close", [])

    out = {}
    for i, ts in enumerate(tss):
        try:
            o = opens[i]; h = highs[i]; l = lows[i]; c = closes[i]
            if None in (o, h, l, c):
                continue
            date_str = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            out[date_str] = {
                "o": round(float(o), 4), "h": round(float(h), 4),
                "l": round(float(l), 4), "c": round(float(c), 4),
            }
        except (TypeError, ValueError, IndexError):
            continue
    return out

def build_dataset(interval, range_or_start, label):
    """Fetch all symbols; return aligned dataset dict."""
    raw = {}
    for lbl, sym in {**COMPANIES, **BENCHES}.items():
        for attempt in range(3):
            try:
                s = fetch(sym, interval, range_or_start)
                if len(s) < 2:
                    print(f"  ! {lbl} ({sym}): too few rows, skipping"); break
                raw[lbl] = s
                print(f"  ok {lbl:<6} {sym:<8} {len(s)} {label} bars  (last: {max(s)})")
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    print(f"  ! {lbl} ({sym}): {e}")

    if not raw:
        return None

    lo = min(min(d) for d in raw.values())
    hi = min(max(d) for d in raw.values())
    master = sorted({d for s in raw.values() for d in s if lo <= d <= hi})

    def aligned(s):
        o, h, l, c, last_c = [], [], [], [], None
        for d in master:
            if d in s:
                bar = s[d]
                last_c = round(bar["c"], 4)
                o.append(round(bar["o"], 4)); h.append(round(bar["h"], 4))
                l.append(round(bar["l"], 4)); c.append(last_c)
            else:
                o.append(None); h.append(None); l.append(None)
                c.append(last_c)
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
    print("Fetching weekly (full history from 1990)…")
    weekly = build_dataset("1wk", "1990-01-01", "weekly")
    if not weekly:
        sys.exit("Weekly fetch failed entirely.")

    print("\nFetching daily (last 12 months)…")
    daily = build_dataset("1d", "1y", "daily")
    if not daily:
        print("  Warning: daily fetch failed — widget will use weekly for all horizons.")
        daily = None

    data = {
        "meta": {
            "source": "finance.yahoo.com",
            "interval": "dual",
            "generated": datetime.datetime.utcnow().isoformat() + "Z",
            "start": weekly["start"], "end": weekly["end"], "ohlc": True,
        },
        "dates":     weekly["dates"],
        "series":    weekly["series"],
        "ohlc":      weekly["ohlc"],
        "benches":   weekly["benches"],
        "benchOhlc": weekly["benchOhlc"],
        "weekly": {k: weekly[k] for k in ("dates","series","ohlc","benches","benchOhlc")},
        "daily":  ({k: daily[k] for k in ("dates","series","ohlc","benches","benchOhlc")}
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
