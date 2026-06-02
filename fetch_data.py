#!/usr/bin/env python3
"""
Fetch real price history into data.json via Yahoo Finance v8 API (stdlib only).

Yahoo Finance caps 1d interval at ~730 days when using period1/period2.
For daily: fetch last 365 days using period1/period2 timestamps.
For weekly: fetch full history from 1990 using period1/period2 timestamps.

Usage:
    python3 fetch_data.py
"""
import json, sys, datetime, time, calendar
import urllib.request, urllib.error

COMPANIES = {
    "INTC": "INTC", "NVDA": "NVDA", "NOK":  "NOK",
    "MSFT": "MSFT", "TSLA": "TSLA", "GOOGL": "GOOGL", "AMD": "AMD",
}
BENCHES = {"SPX": "^GSPC", "DJIA": "^DJI"}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

def fetch(sym, interval, start_date, end_date=None):
    """
    Fetch OHLC data from Yahoo Finance v8 API using period1/period2 timestamps.
    Returns {date_str: {o,h,l,c}}.
    """
    start_ts = int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp())
    if end_date:
        end_ts = int(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86400
    else:
        end_ts = int(datetime.datetime.utcnow().timestamp()) + 86400

    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?interval={interval}&period1={start_ts}&period2={end_ts}")

    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}") from e

    result = d.get("chart", {}).get("result")
    if not result:
        err = d.get("chart", {}).get("error", {})
        raise RuntimeError(f"empty result: {err}")

    result = result[0]
    tss    = result.get("timestamp", [])
    quotes = result["indicators"]["quote"][0]
    opens  = quotes.get("open",  [])
    highs  = quotes.get("high",  [])
    lows   = quotes.get("low",   [])
    closes = quotes.get("close", [])

    out = {}
    for i, ts in enumerate(tss):
        try:
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
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

def build_dataset(interval, start_date, label):
    """Fetch all symbols; return aligned dataset dict."""
    raw = {}
    for lbl, sym in {**COMPANIES, **BENCHES}.items():
        for attempt in range(3):
            try:
                s = fetch(sym, interval, start_date)
                if len(s) < 2:
                    print(f"  ! {lbl} ({sym}): too few rows ({len(s)}), skipping"); break
                raw[lbl] = s
                print(f"  ok {lbl:<6} {sym:<8} {len(s):4} {label} bars  "
                      f"({min(s)} → {max(s)})")
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
                c.append(last_c)  # forward-fill close only
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
    today = datetime.date.today()
    daily_start  = (today - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
    weekly_start = "1990-01-01"

    print(f"Fetching weekly (from {weekly_start})…")
    weekly = build_dataset("1wk", weekly_start, "weekly")
    if not weekly:
        sys.exit("Weekly fetch failed entirely.")

    print(f"\nFetching daily (from {daily_start})…")
    daily = build_dataset("1d", daily_start, "daily")
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
    print(f"\nWrote data.json"
          f"\n  weekly: {w_bars} bars  {weekly['start']} → {weekly['end']}"
          + (f"\n  daily:  {d_bars} bars  {daily['start']} → {daily['end']}" if daily else ""))

if __name__ == "__main__":
    main()
