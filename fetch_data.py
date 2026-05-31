#!/usr/bin/env python3
"""
Fetch real, coarse (monthly by default) price history into data.json,
which index.html loads when present. Keyless source: Stooq CSV endpoint.

Now bakes OHLC (open/high/low/close) so the widget's candlestick view has
real wicks. Closes are also stored separately for the line views.

Usage:
    python3 fetch_data.py            # monthly (default)
    python3 fetch_data.py --weekly
    python3 fetch_data.py --daily
"""
import json, sys, urllib.request, urllib.parse, datetime

COMPANIES = {
    "INTC": "intc.us", "NVDA": "nvda.us", "NOK": "nok.us",
    "MSFT": "msft.us", "TSLA": "tsla.us", "GOOGL": "googl.us", "AMD": "amd.us",
}
BENCHES = {"SPX": "^spx", "DJIA": "^dji"}

interval = "m"
if "--weekly" in sys.argv: interval = "w"
if "--daily"  in sys.argv: interval = "d"

def fetch(symbol):
    """Return {date: {o,h,l,c}} from Stooq CSV (Date,Open,High,Low,Close,Volume)."""
    url = "https://stooq.com/q/d/l/?s=" + urllib.parse.quote(symbol) + "&i=" + interval
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", "replace")
    out = {}
    for line in text.strip().splitlines()[1:]:
        p = line.split(",")
        if len(p) < 5:
            continue
        try:
            out[p[0]] = {"o": float(p[1]), "h": float(p[2]), "l": float(p[3]), "c": float(p[4])}
        except ValueError:
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
            "source": "stooq.com",
            "interval": {"m": "monthly", "w": "weekly", "d": "daily"}[interval],
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
