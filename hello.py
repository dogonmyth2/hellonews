import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


def get_weather(timeout: float = 5.0) -> str:
    """Fetch current location weather info using Open-Meteo API and IP geolocation (with fallback to wttr.in)."""
    try:
        # 1. Geolocation via ip-api
        geo_req = urllib.request.Request("http://ip-api.com/json/", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(geo_req, timeout=timeout) as resp:
            geo = json.loads(resp.read().decode("utf-8"))
            lat, lon = geo["lat"], geo["lon"]
            city = geo.get("city", "Inconnu")
            country = geo.get("country", "Inconnu")

        # 2. Weather via Open-Meteo
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
        )
        w_req = urllib.request.Request(weather_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(w_req, timeout=timeout) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))["current"]
            temp = w_data["temperature_2m"]
            feels_like = w_data["apparent_temperature"]
            humidity = w_data["relative_humidity_2m"]
            code = w_data.get("weather_code", 0)

        wmo_map = {
            0: "Ciel dégagé",
            1: "Principalement dégagé",
            2: "Partiellement nuageux",
            3: "Couvert",
            45: "Brouillard",
            48: "Brouillard givrant",
            51: "Bruine légère",
            53: "Bruine modérée",
            55: "Bruine dense",
            61: "Pluie faible",
            63: "Pluie modérée",
            65: "Pluie forte",
            71: "Neige faible",
            73: "Neige modérée",
            75: "Neige forte",
            80: "Averses de pluie",
            81: "Averses modérées",
            82: "Averses violentes",
            95: "Orage",
        }
        desc = wmo_map.get(code, "Variable")
        return f"Weather in {city}, {country}: {desc}, {temp}°C (feels like {feels_like}°C, humidity {humidity}%)"
    except Exception as e:
        # Fallback to wttr.in
        try:
            wttr_req = urllib.request.Request("https://wttr.in/?format=j1", headers={"User-Agent": "curl/7.68.0"})
            with urllib.request.urlopen(wttr_req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                area = data["nearest_area"][0]["areaName"][0]["value"]
                country = data["nearest_area"][0]["country"][0]["value"]
                cond = data["current_condition"][0]
                temp = cond["temp_C"]
                feels_like = cond["FeelsLikeC"]
                desc = cond["weatherDesc"][0]["value"]
                humidity = cond["humidity"]
                return f"Weather in {area}, {country}: {desc}, {temp}°C (feels like {feels_like}°C, humidity {humidity}%)"
        except Exception:
            return f"[Unable to fetch weather info: {e}]"


def parse_rss_item(item: ET.Element) -> dict:
    """Extract structured data from an RSS item."""
    title_elem = item.find("title")
    link_elem = item.find("link")
    pub_elem = item.find("pubDate")
    source_elem = item.find("source")
    desc_elem = item.find("description")

    title = title_elem.text.strip() if (title_elem is not None and title_elem.text) else "Sans titre"
    link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""
    pub_date = pub_elem.text.strip() if (pub_elem is not None and pub_elem.text) else "Date inconnue"
    source = source_elem.text.strip() if (source_elem is not None and source_elem.text) else "Source inconnue"
    desc_raw = desc_elem.text if (desc_elem is not None and desc_elem.text) else ""
    clean_desc = html.unescape(re.sub(r"<[^>]+>", "", desc_raw)).strip()

    return {
        "title": title,
        "link": link,
        "pub_date": pub_date,
        "source": source,
        "description": clean_desc,
    }


def get_top_news(count: int = 5, timeout: float = 5.0) -> list[dict]:
    """Retrieve top news headlines for France via Google News RSS feed."""
    url = "https://news.google.com/rss?hl=fr&gl=FR&ceid=FR:fr"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            tree = ET.fromstring(response.read())
            items = tree.findall("./channel/item")[:count]
            return [parse_rss_item(it) for it in items]
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
        return [{
            "title": f"[Unable to fetch news: {e}]",
            "link": "",
            "pub_date": "",
            "source": "",
            "description": "",
            "error": True,
        }]


def get_topic_news(topic: str, count: int = 5, timeout: float = 5.0) -> list[dict]:
    """Retrieve top news headlines for a specific topic via Google News RSS feed."""
    encoded_topic = urllib.parse.quote(topic)
    url = f"https://news.google.com/rss/search?q={encoded_topic}&hl=fr&gl=FR&ceid=FR:fr"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            tree = ET.fromstring(response.read())
            items = tree.findall("./channel/item")[:count]
            if not items:
                return [{
                    "title": f"[Aucune actualité trouvée pour le thème '{topic}']",
                    "link": "",
                    "pub_date": "",
                    "source": "",
                    "description": "",
                    "error": True,
                }]
            return [parse_rss_item(it) for it in items]
    except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
        return [{
            "title": f"[Unable to fetch news for '{topic}': {e}]",
            "link": "",
            "pub_date": "",
            "source": "",
            "description": "",
            "error": True,
        }]


def format_news_detail(item: dict, theme: str, number: int) -> str:
    """Format full details of a news article."""
    title = item.get("title", "Sans titre")
    source = item.get("source", "Source inconnue")
    pub_date = item.get("pub_date", "Date inconnue")
    link = item.get("link", "")
    desc = item.get("description", "")

    sep = "=" * 60
    lines = [
        f"\n{sep}",
        f"DÉTAIL DE L'ACTUALITÉ [Thème : {theme} | N°{number}]",
        f"{sep}",
        f"Titre   : {title}",
        f"Source  : {source}",
        f"Date    : {pub_date}",
        f"Lien    : {link}",
    ]
    if desc:
        lines.append(f"Extrait : {desc}")
    lines.append(f"{sep}")
    return "\n".join(lines)


def show_news_detail(theme: str, number: int, news_store: dict) -> None:
    """Display the details of a news article by theme and 1-based index."""
    matched_key = None
    for key in news_store:
        if key.strip().lower() == theme.strip().lower():
            matched_key = key
            break

    if not matched_key:
        print(f"\n[Recherche d'actualités pour le thème '{theme}'...]")
        items = get_topic_news(theme, count=max(number, 5))
        if items and not items[0].get("error"):
            news_store[theme] = items
            matched_key = theme
        else:
            print(f"[Erreur : Impossible de trouver ou récupérer le thème '{theme}']")
            return

    articles = news_store[matched_key]
    if not articles or articles[0].get("error"):
        print(f"[Erreur : Aucun article valide disponible pour '{matched_key}']")
        return

    if 1 <= number <= len(articles):
        print(format_news_detail(articles[number - 1], matched_key, number))
    else:
        print(f"[Erreur : Numéro {number} invalide pour le thème '{matched_key}' (disponibles : 1 à {len(articles)})]")


def load_config(config_path: Path | None = None) -> dict:
    """Load configuration dictionary from appconfig.json."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent / "appconfig.json"

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"[Avertissement configuration: impossible de charger {config_path}: {e}]")
        return {}


def get_news_topics(config: dict) -> list[str]:
    """Retrieve news topics from config with fallback to ['agentic AI']."""
    topics = config.get("news_topics")
    if not topics:
        return ["agentic AI"]
    if isinstance(topics, str):
        return [topics.strip()] if topics.strip() else ["agentic AI"]
    cleaned = [t.strip() for t in topics if isinstance(t, str) and t.strip()]
    return cleaned if cleaned else ["agentic AI"]


def get_news_count(config: dict, cli_count: int | None = None, default: int = 5) -> int:
    """Retrieve and validate the number of news to fetch from CLI or config."""
    if cli_count is not None:
        try:
            val = int(cli_count)
            if val > 0:
                return min(val, 20)
        except (ValueError, TypeError):
            pass

    count_cfg = config.get("top_news_count")
    if count_cfg is None:
        count_cfg = config.get("news_count")

    if count_cfg is not None:
        try:
            val = int(count_cfg)
            if val > 0:
                return min(val, 20)
        except (ValueError, TypeError):
            pass

    return default


def parse_cli_args(args: list[str]) -> tuple[int | None, str | None, int | None]:
    """Parse CLI arguments for news count and news detail.

    Returns:
        (cli_count, detail_theme, detail_number)
    """
    cli_count = None
    detail_theme = None
    detail_number = None

    i = 0
    remaining = []
    while i < len(args):
        arg = args[i]
        if arg in ("--count", "-n", "-c") and i + 1 < len(args):
            try:
                cli_count = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg.startswith("--count=") or arg.startswith("-n="):
            _, _, val = arg.partition("=")
            try:
                cli_count = int(val)
            except ValueError:
                pass
            i += 1
        elif arg in ("--detail", "-d") and i + 2 < len(args):
            detail_theme = args[i + 1]
            try:
                detail_number = int(args[i + 2])
            except ValueError:
                print(f"[Erreur : '{args[i + 2]}' n'est pas un numéro valide.]")
            i += 3
        else:
            remaining.append(arg)
            i += 1

    # Check positional shorthand: e.g. "python hello.py France 1"
    if detail_theme is None and len(remaining) >= 2 and not remaining[0].startswith("-"):
        detail_theme = remaining[0]
        try:
            detail_number = int(remaining[1])
        except ValueError:
            print(f"[Erreur : '{remaining[1]}' n'est pas un numéro valide.]")

    return cli_count, detail_theme, detail_number


def load_stock_config(config_path: Path | None = None, config: dict | None = None) -> list[dict]:
    """Load stock symbols and names from configuration."""
    if config is None:
        config = load_config(config_path)
    return config.get("stocks", [])


def get_stock_quotes(stocks: list[dict], timeout: float = 5.0) -> list[str]:
    """Retrieve stock prices and daily change from Yahoo Finance chart API."""
    if not stocks:
        return ["[Aucune action configurée dans appconfig.json]"]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    results = []

    for stock in stocks:
        name = stock.get("name", "Action")
        symbol = stock.get("symbol", "")
        if not symbol:
            continue

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                meta = payload["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice")
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                currency = meta.get("currency", "EUR")

                if price is not None and prev is not None:
                    change = price - prev
                    pct = (change / prev) * 100 if prev else 0.0
                    results.append(
                        f"{name} ({symbol}): {price:.2f} {currency} ({change:+.2f} {currency}, {pct:+.2f}%)"
                    )
                elif price is not None:
                    results.append(f"{name} ({symbol}): {price:.2f} {currency}")
                else:
                    results.append(f"{name} ({symbol}): [Cours indisponible]")
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as e:
            results.append(f"{name} ({symbol}): [Erreur de récupération: {e}]")

    return results


def main():
    print("Hello, World!")
    print(get_weather())

    config = load_config()

    cli_count, detail_theme, detail_number = parse_cli_args(sys.argv[1:])
    news_count = get_news_count(config, cli_count=cli_count)

    news_store = {}

    france_news = get_top_news(news_count)
    news_store["France"] = france_news
    print(f"\nTop {news_count} News (France):")
    for i, item in enumerate(france_news, 1):
        print(f"  {i}. {item['title']}")

    topics = get_news_topics(config)
    for topic in topics:
        topic_news = get_topic_news(topic, news_count)
        news_store[topic] = topic_news
        print(f"\nTop {news_count} News (Thème: {topic}):")
        for i, item in enumerate(topic_news, 1):
            print(f"  {i}. {item['title']}")

    print("\nCours de bourse :")
    stocks = load_stock_config(config=config)
    for quote in get_stock_quotes(stocks):
        print(f"  • {quote}")

    # Consultation détaillée d'une actualité (CLI ou prompt final)
    if detail_theme is not None and detail_number is not None:
        show_news_detail(detail_theme, detail_number, news_store)
    elif detail_theme is None:
        try:
            print("\n--- Consultation détaillée d'une actualité ---")
            themes_str = ", ".join(f"'{k}'" for k in news_store.keys())
            prompt = (
                f"Entrez le thème et le numéro (ex: 'agentic AI 1', thèmes: {themes_str})\n"
                "ou appuyez sur Entrée pour quitter : "
            )
            user_input = input(prompt).strip()
            if user_input:
                parts = user_input.rsplit(maxsplit=1)
                if len(parts) == 2 and parts[1].isdigit():
                    show_news_detail(parts[0], int(parts[1]), news_store)
                elif parts[0].isdigit() and len(news_store) == 1:
                    first_theme = list(news_store.keys())[0]
                    show_news_detail(first_theme, int(parts[0]), news_store)
                else:
                    print("[Format attendu : <theme> <numero>, ex: 'agentic AI 1' ou 'France 2']")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
