"""Freeze Yahoo Finance daily bars for the exact course universe; stdlib only."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, time, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "study_config.json"
STUDY = json.loads(CONFIG.read_text(encoding="utf-8"))
RAW = ROOT / "data" / "raw"
FIELDS = ("symbol", "date", "open", "high", "low", "close", "volume", "adjusted")
START = date.fromisoformat(STUDY["download_start"])
HOST = "https://query1.finance.yahoo.com/v8/finance/chart/"


def symbols():
    tickers = STUDY["symbols"]
    benchmark = STUDY["benchmark"]
    if len(tickers) != 95 or len(set(tickers)) != 95 or benchmark in tickers:
        raise ValueError("Unexpected course universe")
    return tickers + [benchmark]


def epoch(d):
    return int(datetime.combine(d, time.min, tzinfo=timezone.utc).timestamp())


def fetch(symbol, end, refresh=False):
    params = urlencode({"period1": epoch(START), "period2": epoch(end + timedelta(days=1)),
                        "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"})
    url = f"{HOST}{symbol}?{params}"
    raw_path = RAW / f"{symbol}.json.gz"
    meta_path = RAW / f"{symbol}.provenance.json"
    if not refresh and raw_path.exists() and meta_path.exists():
        prior = json.loads(meta_path.read_text(encoding="utf-8"))
        if prior["url"] == url:
            data = gzip.decompress(raw_path.read_bytes())
            if hashlib.sha256(data).hexdigest() != prior["sha256"]:
                raise ValueError("Cached payload hash mismatch")
            return data, prior
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urlopen(request, timeout=25) as response:
            data = response.read()
            response_date = response.headers.get("Date")
    except HTTPError as exc:
        detail = f"HTTP {exc.code}"
        if exc.headers.get("Retry-After"):
            detail += f"; retry after {exc.headers.get('Retry-After')}"
        raise RuntimeError(detail) from None
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from None
    provenance = {"symbol": symbol, "url": url, "http_date": response_date,
                  "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                  "sha256": hashlib.sha256(data).hexdigest()}
    # Validate structure before caching a success.
    parse(data, symbol, end)
    raw_path.write_bytes(gzip.compress(data, mtime=0))
    meta_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return data, provenance


def parse(data, symbol, end):
    chart = json.loads(data)["chart"]
    if chart.get("error") or not chart.get("result"):
        raise ValueError(f"Provider error: {chart.get('error')}")
    record = chart["result"][0]
    meta = record["meta"]
    if meta.get("symbol") != symbol or meta.get("currency") != "USD":
        raise ValueError(f"Unexpected instrument metadata: {meta.get('symbol')}, {meta.get('currency')}")
    try:
        tz = ZoneInfo(meta["exchangeTimezoneName"])
    except ZoneInfoNotFoundError:
        if meta["exchangeTimezoneName"] != "America/New_York":
            raise
        # US regular-session open is 13:30/14:30 UTC, on the same
        # calendar date as in New York. Assert that convention below.
        tz = timezone.utc
    ts = record["timestamp"]
    ohlcv = record["indicators"]["quote"][0]
    cols = [ohlcv[k] for k in FIELDS[2:-1]] + [record["indicators"]["adjclose"][0]["adjclose"]]
    if not ts or any(len(col) != len(ts) for col in cols):
        raise ValueError("Empty series or mismatched field lengths")
    rows = []
    for t, *values in zip(ts, *cols, strict=True):
        dt = datetime.fromtimestamp(t, tz)
        if tz == timezone.utc and dt.hour not in (13, 14, 15, 16, 17, 18, 19, 20, 21):
            raise ValueError("Unexpected UTC timestamp for a US regular-session bar")
        if START <= dt.date() <= end:
            rows.append((symbol, dt.date().isoformat(), *values))
    if not rows:
        raise ValueError("No prices within range")
    return rows, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", default=STUDY["study_data_through"], type=date.fromisoformat,
                        help="Inclusive US trading date; defaults to the study cutoff")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.end < START:
        parser.error("--end must be on or after the start")
    RAW.mkdir(parents=True, exist_ok=True)
    universe = symbols()
    manifest = {"source": "Yahoo Finance daily chart data (USD)", "start_requested": str(START),
                "end_inclusive": str(args.end), "tickers": universe,
                "study_config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(), "series": {}}

    def download(ticker):
        try:
            data, provenance = fetch(ticker, args.end, args.refresh)
            rows, meta = parse(data, ticker, args.end)
            return rows, {**provenance, "rows": len(rows), "first": rows[0][1], "last": rows[-1][1],
                          "exchange": meta.get("fullExchangeName"),
                          "regular_market_time_utc": datetime.fromtimestamp(
                              meta["regularMarketTime"], timezone.utc).isoformat()}
        except Exception as exc:
            return [], {"error": f"{type(exc).__name__}: {exc}"}

    all_rows = []
    # Small batches keep load modest. Stop initiating new requests on a provider limit.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(universe), 4):
            batch = universe[start:start + 4]
            for ticker, (rows, detail) in zip(batch, pool.map(download, batch), strict=True):
                manifest["series"][ticker] = detail
                all_rows.extend(rows)
                print(ticker, len(rows), detail.get("error", detail.get("last", "")), flush=True)
            if any("HTTP 429" in manifest["series"][ticker].get("error", "") for ticker in batch):
                for ticker in universe[start + 4:]:
                    manifest["series"][ticker] = {"error": "Not requested after provider rate limit"}
                break
    failed = [ticker for ticker in universe if "error" in manifest["series"][ticker]]
    manifest["failed"] = failed
    manifest["rows"] = len(all_rows)
    csv_path = ROOT / "data" / ("daily_prices.partial.csv" if failed else "daily_prices.csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(all_rows)
    manifest["csv"] = csv_path.name
    manifest["csv_sha256"] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    (ROOT / "data" / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(universe) - len(failed)}/{len(universe)} series, {len(all_rows)} rows; failed={failed}")
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
