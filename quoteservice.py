#!/data/data/com.termux/files/usr/bin/env python3
"""Standalone stock quote service matching hello.py's Yahoo Finance integration.

Zero external dependencies (pure Python 3 standard library).
Can be run as a CLI tool or imported as a module.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_TIMEOUT = 5.0
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "hellodb.db"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration dictionary from appconfig.json."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent / "appconfig.json"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(
            f"[Avertissement configuration: impossible de charger {config_path}: {e}]",
            file=sys.stderr,
        )
        return {}


def load_stock_config(
    config_path: Path | None = None, config: dict | None = None
) -> list[dict]:
    """Load stock symbols and names from configuration."""
    if config is None:
        config = load_config(config_path)
    return config.get("stocks", [])


def _fetch_chart_result(
    symbol: str, query_params: str, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Fetch and return the first chart result object from Yahoo Finance."""
    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?{query_params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["chart"]["result"][0]


def fetch_stock_quote(
    symbol: str, name: str | None = None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Fetch a single stock quote from Yahoo Finance chart API."""
    clean_symbol = symbol.strip().upper()
    display_name = name.strip() if (name and name.strip()) else clean_symbol

    result = {
        "name": display_name,
        "symbol": clean_symbol,
        "price": None,
        "previous_close": None,
        "change": None,
        "change_pct": None,
        "currency": None,
        "error": None,
    }

    try:
        chart = _fetch_chart_result(clean_symbol, "interval=1d&range=1d", timeout=timeout)
        meta = chart["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        currency = meta.get("currency", "EUR")

        if not (name and name.strip()):
            display_name = meta.get("shortName") or meta.get("symbol", clean_symbol)
            result["name"] = display_name

        result["price"] = price
        result["previous_close"] = prev
        result["currency"] = currency

        if price is not None and prev is not None:
            change = price - prev
            pct = (change / prev) * 100 if prev else 0.0
            result["change"] = change
            result["change_pct"] = pct
        elif price is None:
            result["error"] = "Cours indisponible"
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
    ) as e:
        result["error"] = f"Erreur de récupération: {e}"

    return result


def parse_iso_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD date string into a UTC-aware datetime at 00:00:00Z."""
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)


def fetch_stock_history(
    symbol: str,
    start_date: str,
    end_date: str,
    name: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Fetch daily open and close prices for a symbol over [start_date, end_date]."""
    clean_symbol = symbol.strip().upper()
    display_name = name.strip() if (name and name.strip()) else clean_symbol

    result = {
        "name": display_name,
        "symbol": clean_symbol,
        "currency": None,
        "start_date": start_date,
        "end_date": end_date,
        "history": [],
        "error": None,
    }

    try:
        start_dt = parse_iso_date(start_date)
        end_dt = parse_iso_date(end_date)
        if start_dt > end_dt:
            result["error"] = f"Plage de dates invalide: {start_date} > {end_date}"
            return result

        period1 = int(start_dt.timestamp())
        period2 = int((end_dt + timedelta(days=1)).timestamp())
        chart = _fetch_chart_result(
            clean_symbol,
            f"period1={period1}&period2={period2}&interval=1d",
            timeout=timeout,
        )
        meta = chart["meta"]
        result["currency"] = meta.get("currency", "EUR")
        if not (name and name.strip()):
            result["name"] = meta.get("shortName") or meta.get("symbol", clean_symbol)

        timestamps = chart.get("timestamp") or []
        quote_data = (chart.get("indicators", {}).get("quote") or [{}])[0]
        opens = quote_data.get("open") or []
        closes = quote_data.get("close") or []

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")
        rows = []
        for idx, ts in enumerate(timestamps):
            day_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            if not (start_str <= day_str <= end_str):
                continue
            open_val = opens[idx] if idx < len(opens) else None
            close_val = closes[idx] if idx < len(closes) else None
            if open_val is None and close_val is None:
                continue
            rows.append({"date": day_str, "open": open_val, "close": close_val})

        result["history"] = rows
    except ValueError as e:
        result["error"] = f"Date invalide (attendu YYYY-MM-DD): {e}"
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
    ) as e:
        result["error"] = f"Erreur de récupération: {e}"

    return result


def format_stock_history(history_data: dict) -> str:
    """Format a historical quote dict into a human-readable string."""
    name = history_data["name"]
    symbol = history_data["symbol"]
    start_date = history_data["start_date"]
    end_date = history_data["end_date"]
    error = history_data.get("error")

    if error:
        return f"{name} ({symbol}) [{start_date} -> {end_date}]: [{error}]"

    currency = history_data.get("currency") or "EUR"
    rows = history_data.get("history", [])
    header = f"{name} ({symbol}) [{start_date} -> {end_date}] ({currency}):"
    if not rows:
        return f"{header}\n    [Aucune donnée disponible sur cette période]"

    lines = [header]
    for row in rows:
        open_str = f"{row['open']:.2f}" if row["open"] is not None else "N/A"
        close_str = f"{row['close']:.2f}" if row["close"] is not None else "N/A"
        lines.append(f"    {row['date']} : Open {open_str} | Close {close_str}")
    return "\n".join(lines)


def format_stock_quote(quote: dict) -> str:
    """Format a structured quote dict into the same human-readable string as hello.py."""
    name = quote["name"]
    symbol = quote["symbol"]
    error = quote.get("error")

    if error:
        return f"{name} ({symbol}): [{error}]"

    price = quote["price"]
    currency = quote.get("currency") or "EUR"
    change = quote.get("change")
    pct = quote.get("change_pct")

    if price is not None and change is not None and pct is not None:
        return f"{name} ({symbol}): {price:.2f} {currency} ({change:+.2f} {currency}, {pct:+.2f}%)"
    if price is not None:
        return f"{name} ({symbol}): {price:.2f} {currency}"
    return f"{name} ({symbol}): [Cours indisponible]"


def get_stock_quotes(
    stocks: list[dict], timeout: float = DEFAULT_TIMEOUT
) -> list[str]:
    """Retrieve stock prices and daily change from Yahoo Finance chart API."""
    if not stocks:
        return ["[Aucune action configurée dans appconfig.json]"]

    results = []
    for stock in stocks:
        symbol = stock.get("symbol", "")
        if not symbol or not symbol.strip():
            continue
        name = stock.get("name", "Action")
        quote = fetch_stock_quote(symbol=symbol, name=name, timeout=timeout)
        results.append(format_stock_quote(quote))
    return results


def _ensure_stock_quotes_table(conn: sqlite3.Connection) -> None:
    """Ensure the stock_quotes table and symbol/date index exist."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            open_price REAL,
            close_price REAL,
            currency TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (quote_date, symbol)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_quotes_symbol_date
            ON stock_quotes (symbol, quote_date);
        """
    )


def sync_stock_history_to_db(
    start_date: str,
    end_date: str,
    config_path: Path | None = None,
    db_path: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Retrieve open/close history for all appconfig.json stocks and upsert into hellodb.db."""
    target_db = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    stocks = [
        s
        for s in load_stock_config(config_path=config_path)
        if s.get("symbol") and s["symbol"].strip()
    ]

    rows_upserted = 0
    errors: list[dict] = []

    with sqlite3.connect(target_db) as conn:
        _ensure_stock_quotes_table(conn)
        for stock in stocks:
            hist = fetch_stock_history(
                symbol=stock["symbol"],
                start_date=start_date,
                end_date=end_date,
                name=stock.get("name"),
                timeout=timeout,
            )
            if hist.get("error"):
                errors.append({"symbol": hist["symbol"], "error": hist["error"]})
                continue

            currency = hist.get("currency")
            upsert_rows = [
                (
                    row["date"],
                    hist["symbol"],
                    row.get("open"),
                    row.get("close"),
                    currency,
                )
                for row in hist.get("history", [])
            ]
            if upsert_rows:
                conn.executemany(
                    """
                    INSERT INTO stock_quotes (quote_date, symbol, open_price, close_price, currency)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(quote_date, symbol) DO UPDATE SET
                        open_price = excluded.open_price,
                        close_price = excluded.close_price,
                        currency = excluded.currency
                    """,
                    upsert_rows,
                )
                rows_upserted += len(upsert_rows)
        conn.commit()

    return {
        "db_path": str(target_db),
        "start_date": start_date,
        "end_date": end_date,
        "stocks_processed": len(stocks),
        "rows_upserted": rows_upserted,
        "errors": errors,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Service autonome de récupération des cours de bourse (Yahoo Finance)."
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Symboles boursiers à interroger (ex: GLE.PA AIR.PA AAPL). Si omis, lit appconfig.json.",
    )
    parser.add_argument(
        "-s",
        "--symbol",
        action="append",
        dest="flag_symbols",
        default=[],
        help="Symbole boursier supplémentaire (option répétable).",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Chemin vers un fichier de configuration JSON (défaut: appconfig.json).",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Délai d'attente HTTP en secondes (défaut: {DEFAULT_TIMEOUT}).",
    )
    parser.add_argument(
        "--from",
        "--start-date",
        dest="start_date",
        default=None,
        help="Date de début de l'historique (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to",
        "--end-date",
        dest="end_date",
        default=None,
        help="Date de fin de l'historique (YYYY-MM-DD, défaut: aujourd'hui UTC).",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Enregistrer l'historique des actions de appconfig.json dans hellodb.db.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Chemin vers la base SQLite (défaut: hellodb.db).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Afficher la sortie au format JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    if args.end_date and not args.start_date:
        print(
            "Erreur : --to/--end-date nécessite --from/--start-date.",
            file=sys.stderr,
        )
        return 2
    if args.save_db and not args.start_date:
        print(
            "Erreur : --save-db nécessite --from/--start-date.",
            file=sys.stderr,
        )
        return 2

    cli_symbols = [s.strip() for s in (*args.symbols, *args.flag_symbols) if s.strip()]

    if args.start_date and args.save_db:
        end_date = args.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary = sync_stock_history_to_db(
            start_date=args.start_date,
            end_date=end_date,
            config_path=args.config,
            db_path=args.db,
            timeout=args.timeout,
        )
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0 if not summary["errors"] else 1

        print(
            f"Synchronisation terminée ({summary['start_date']} -> {summary['end_date']}) : "
            f"{summary['rows_upserted']} ligne(s) enregistrée(s) pour {summary['stocks_processed']} action(s) dans {summary['db_path']}."
        )
        for err in summary["errors"]:
            print(f"  • Erreur ({err['symbol']}): {err['error']}", file=sys.stderr)
        return 0 if not summary["errors"] else 1

    if cli_symbols:
        stocks = [{"name": None, "symbol": sym} for sym in cli_symbols]
    else:
        stocks = load_stock_config(config_path=args.config)

    valid_stocks = [
        s for s in stocks if s.get("symbol") and s["symbol"].strip()
    ]

    if args.start_date:
        end_date = args.end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        histories = [
            fetch_stock_history(
                symbol=s["symbol"],
                start_date=args.start_date,
                end_date=end_date,
                name=s.get("name"),
                timeout=args.timeout,
            )
            for s in valid_stocks
        ]
        if args.json:
            print(json.dumps(histories, indent=2, ensure_ascii=False))
            return 0

        print(f"Historique des cours ({args.start_date} -> {end_date}) :")
        if not histories:
            print("  • [Aucune action configurée dans appconfig.json]")
        else:
            for hist in histories:
                print(f"  • {format_stock_history(hist)}")
        return 0

    if args.json:
        quotes = [
            fetch_stock_quote(
                symbol=s["symbol"],
                name=s.get("name"),
                timeout=args.timeout,
            )
            for s in valid_stocks
        ]
        print(json.dumps(quotes, indent=2, ensure_ascii=False))
        return 0

    print("Cours de bourse :")
    for line in get_stock_quotes(stocks, timeout=args.timeout):
        print(f"  • {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
