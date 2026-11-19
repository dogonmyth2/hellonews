#!/data/data/com.termux/files/usr/bin/env python3
"""Standalone stock quote service matching hello.py's Yahoo Finance integration.

Zero external dependencies (pure Python 3 standard library).
Can be run as a CLI tool or imported as a module.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_TIMEOUT = 5.0
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


def fetch_stock_quote(
    symbol: str, name: str | None = None, timeout: float = DEFAULT_TIMEOUT
) -> dict:
    """Fetch a single stock quote from Yahoo Finance chart API."""
    clean_symbol = symbol.strip().upper()
    display_name = name.strip() if (name and name.strip()) else clean_symbol
    encoded_symbol = urllib.parse.quote(clean_symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

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
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            meta = payload["chart"]["result"][0]["meta"]
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
        "--json",
        action="store_true",
        help="Afficher la sortie au format JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    cli_symbols = [s.strip() for s in (*args.symbols, *args.flag_symbols) if s.strip()]

    if cli_symbols:
        stocks = [{"name": None, "symbol": sym} for sym in cli_symbols]
    else:
        stocks = load_stock_config(config_path=args.config)

    if args.json:
        quotes = [
            fetch_stock_quote(
                symbol=s["symbol"],
                name=s.get("name"),
                timeout=args.timeout,
            )
            for s in stocks
            if s.get("symbol") and s["symbol"].strip()
        ]
        print(json.dumps(quotes, indent=2, ensure_ascii=False))
        return 0

    print("Cours de bourse :")
    for line in get_stock_quotes(stocks, timeout=args.timeout):
        print(f"  • {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
