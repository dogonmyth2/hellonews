#!/data/data/com.termux/files/usr/bin/env python3
"""Standalone Model Context Protocol (MCP) Server.

Provides tools for real-time weather, stock quotes, news, and system info.
Supports both Streamable HTTP transport (default) and Stdio transport (--stdio).
Supports true daemon background execution (--daemon).
Zero external dependencies (pure Python 3 standard library).
"""

import argparse
import html
import http.server
import json
import logging
import os
import platform
import re
import socket
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mcp_server")

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "standalone-tools-mcp"
SERVER_VERSION = "1.0.0"

WMO_WEATHER_MAP = {
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


# ==============================================================================
# TOOL IMPLEMENTATIONS
# ==============================================================================

def tool_get_weather(city: str | None = None) -> str:
    """Fetch current weather for a city or current location via Open-Meteo & IP."""
    timeout = 5.0
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        if city and city.strip():
            city_query = city.strip()
            geo_url = (
                f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_query)}"
                "&count=1&language=fr&format=json"
            )
            req = urllib.request.Request(geo_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("results")
                if not results:
                    return f"Erreur : Ville '{city_query}' introuvable."
                first = results[0]
                lat, lon = first["latitude"], first["longitude"]
                location_name = f"{first.get('name', city_query)}, {first.get('country', '')}"
        else:
            # Automatic geolocation via ip-api
            req = urllib.request.Request("http://ip-api.com/json/", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                lat, lon = data["lat"], data["lon"]
                location_name = f"{data.get('city', 'Inconnu')}, {data.get('country', 'Inconnu')}"

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code"
        )
        w_req = urllib.request.Request(weather_url, headers=headers)
        with urllib.request.urlopen(w_req, timeout=timeout) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))["current"]
            temp = w_data["temperature_2m"]
            feels = w_data["apparent_temperature"]
            hum = w_data["relative_humidity_2m"]
            code = w_data.get("weather_code", 0)
            desc = WMO_WEATHER_MAP.get(code, "Variable")

        return f"Météo à {location_name} : {desc}, {temp}°C (ressenti {feels}°C, humidité {hum}%)"
    except Exception as e:
        return f"Erreur météo : {e}"


def tool_get_stock_quote(symbol: str) -> str:
    """Fetch live stock price and daily change from Yahoo Finance."""
    symbol = symbol.strip().upper()
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            currency = meta.get("currency", "EUR")
            short_name = meta.get("shortName") or meta.get("symbol", symbol)

            if price is not None and prev is not None:
                change = price - prev
                pct = (change / prev) * 100 if prev else 0.0
                return f"{short_name} ({symbol}): {price:.2f} {currency} ({change:+.2f} {currency}, {pct:+.2f}%)"
            elif price is not None:
                return f"{short_name} ({symbol}): {price:.2f} {currency}"
            return f"Cours indisponible pour le symbole {symbol}."
    except Exception as e:
        return f"Erreur récupération bourse ({symbol}) : {e}"


def load_default_news_count() -> int:
    """Load default news count from appconfig.json if available."""
    try:
        config_path = Path(__file__).resolve().parent / "appconfig.json"
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                val = cfg.get("top_news_count") or cfg.get("news_count")
                if val is not None:
                    parsed = int(val)
                    if parsed > 0:
                        return min(parsed, 10)
    except Exception:
        pass
    return 5


def tool_get_news(topic: str = "agentic AI", count: int | None = None) -> str:
    """Retrieve top news articles for a query or general France news."""
    if count is None:
        count = load_default_news_count()
    count = max(1, min(count, 10))
    topic_clean = topic.strip()
    if topic_clean.lower() in ("france", "actu france"):
        url = "https://news.google.com/rss?hl=fr&gl=FR&ceid=FR:fr"
    else:
        encoded = urllib.parse.quote(topic_clean)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=fr&gl=FR&ceid=FR:fr"

    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            tree = ET.fromstring(resp.read())
            items = tree.findall("./channel/item")[:count]
            if not items:
                return f"Aucune actualité trouvée pour '{topic_clean}'."

            lines = [f"Top {len(items)} Actualités ({topic_clean}) :"]
            for i, it in enumerate(items, 1):
                title = it.find("title").text if it.find("title") is not None else "Sans titre"
                lines.append(f"{i}. {title}")
            return "\n".join(lines)
    except Exception as e:
        return f"Erreur actualités ({topic_clean}) : {e}"


def tool_get_system_info() -> str:
    """Return host system information, architecture, Python version, and network."""
    hostname = socket.gethostname()
    os_name = platform.system()
    os_release = platform.release()
    arch = platform.machine()
    py_ver = sys.version.split()[0]

    uptime = "Inconnu"
    try:
        with open("/proc/uptime", "r") as f:
            sec = float(f.readline().split()[0])
            hours = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            uptime = f"{hours}h {mins}m"
    except Exception:
        pass

    info = [
        f"Hôte        : {hostname}",
        f"Système     : {os_name} {os_release} ({arch})",
        f"Python      : {py_ver}",
        f"PID Serveur : {os.getpid()}",
        f"Uptime      : {uptime}",
        f"Dossier CWD : {os.getcwd()}",
    ]
    return "\n".join(info)


# ==============================================================================
# MCP PROTOCOL DEFINITIONS & DISPATCHER
# ==============================================================================

TOOLS_METADATA = [
    {
        "name": "get_weather",
        "description": "Obtenir la météo en temps réel (température, ressenti, ciel, humidité) pour la position actuelle ou pour une ville donnée.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nom optionnel de la ville (ex: Paris, Lyon, Marseille). Si omis, utilise la position actuelle.",
                }
            },
        },
    },
    {
        "name": "get_stock_quote",
        "description": "Obtenir le cours de bourse en direct et la variation quotidienne d'une action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbole boursier (ex: GLE.PA pour Société Générale, AIR.PA pour Airbus, AI.PA pour Air Liquide, AAPL, MSFT).",
                }
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_news",
        "description": "Récupérer les principaux titres d'actualités récents par mot-clé thématique ou pour la France.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Thème ou mot-clé de recherche (ex: agentic AI, Google Antigravity, France).",
                },
                "count": {
                    "type": "integer",
                    "description": "Nombre d'articles à retourner (1 à 10, défaut 5).",
                },
            },
        },
    },
    {
        "name": "get_system_info",
        "description": "Obtenir des informations système sur l'hôte et l'environnement Termux/Linux.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_tool_call(name: str, arguments: dict) -> dict:
    """Execute tool and wrap response in MCP result structure."""
    try:
        if name == "get_weather":
            city = arguments.get("city")
            output = tool_get_weather(city=city)
        elif name == "get_stock_quote":
            symbol = arguments.get("symbol")
            if not symbol:
                return {"content": [{"type": "text", "text": "Erreur : Paramètre 'symbol' requis."}], "isError": True}
            output = tool_get_stock_quote(symbol=symbol)
        elif name == "get_news":
            topic = arguments.get("topic", "agentic AI")
            count = arguments.get("count")
            output = tool_get_news(topic=topic, count=count)
        elif name == "get_system_info":
            output = tool_get_system_info()
        else:
            return {
                "content": [{"type": "text", "text": f"Erreur : Outil '{name}' inconnu."}],
                "isError": True,
            }

        return {
            "content": [{"type": "text", "text": output}],
            "isError": False,
        }
    except Exception as e:
        logger.exception("Error executing tool %s", name)
        return {
            "content": [{"type": "text", "text": f"Exception lors de l'exécution de l'outil : {e}"}],
            "isError": True,
        }


def process_jsonrpc_message(msg: dict) -> dict | None:
    """Process a JSON-RPC 2.0 message according to MCP specification."""
    req_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if not method:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600, "message": "Invalid Request: method missing"}}

    if method == "notifications/initialized":
        logger.info("Client completed initialization.")
        return None

    if method == "initialize":
        logger.info("Handling 'initialize' request from client.")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    elif method == "tools/list":
        logger.info("Handling 'tools/list' request.")
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_METADATA,
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        logger.info("Handling 'tools/call' for tool '%s'", tool_name)
        result = handle_tool_call(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    else:
        logger.warning("Method '%s' not implemented.", method)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }


# ==============================================================================
# HTTP TRANSPORT HANDLER
# ==============================================================================

class MCPHttpHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler supporting MCP Streamable HTTP."""

    def log_message(self, format, *args):
        logger.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)

    def do_GET(self):
        """Health check and status endpoint."""
        if self.path in ("/", "/health", "/mcp/health"):
            data = {
                "status": "healthy",
                "service": SERVER_NAME,
                "version": SERVER_VERSION,
                "protocol": PROTOCOL_VERSION,
                "pid": os.getpid(),
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health",
                },
                "available_tools": [t["name"] for t in TOOLS_METADATA],
            }
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Endpoint non trouvé. Utilisez /mcp pour les requêtes JSON-RPC.")

    def do_POST(self):
        """MCP JSON-RPC 2.0 endpoint."""
        if self.path in ("/mcp", "/"):
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_error(400, "Content-Length requis.")
                return

            try:
                raw_body = self.rfile.read(content_len).decode("utf-8")
                payload = json.loads(raw_body)
            except Exception as e:
                self.send_error(400, f"JSON malformé : {e}")
                return

            response_data = process_jsonrpc_message(payload)

            if response_data is None:
                self.send_response(204)
                self.end_headers()
                return

            body = json.dumps(response_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Endpoint inconnu.")


# ==============================================================================
# STDIO TRANSPORT HANDLER
# ==============================================================================

def run_stdio_server():
    """Run MCP server in standard input/output mode."""
    logger.info("Démarrage du serveur MCP en mode STDIO...")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue

            msg = json.loads(line_str)
            resp = process_jsonrpc_message(msg)
            if resp is not None:
                out_line = json.dumps(resp) + "\n"
                sys.stdout.write(out_line)
                sys.stdout.flush()
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            logger.exception("Erreur boucle stdio: %s", e)


# ==============================================================================
# DAEMON HELPER
# ==============================================================================

def daemonize(pidfile: str | None = None, logfile: str | None = None):
    """Detach process from terminal as a true background daemon."""
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)

    sys.stdout.flush()
    sys.stderr.flush()

    if logfile:
        log_fd = open(logfile, "a+", encoding="utf-8")
        os.dup2(log_fd.fileno(), sys.stdout.fileno())
        os.dup2(log_fd.fileno(), sys.stderr.fileno())

    if pidfile:
        with open(pidfile, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Serveur MCP autonome (Model Context Protocol)")
    parser.add_argument("--stdio", action="store_true", help="Activer le mode Stdio au lieu du serveur HTTP")
    parser.add_argument("--daemon", action="store_true", help="Détacher le processus en arrière-plan (mode démon)")
    parser.add_argument("--pidfile", help="Chemin du fichier PID")
    parser.add_argument("--logfile", help="Chemin du fichier journal")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'écoute HTTP (défaut: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port d'écoute HTTP (défaut: 8765)")
    args = parser.parse_args()

    if args.stdio:
        run_stdio_server()
        return

    if args.daemon:
        daemonize(pidfile=args.pidfile, logfile=args.logfile)
    elif args.pidfile:
        with open(args.pidfile, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

    host, port = args.host, args.port
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.ThreadingTCPServer((host, port), MCPHttpHandler) as server:
            logger.info("=" * 60)
            logger.info("Serveur MCP autonome démarré avec succès !")
            logger.info("URL MCP : http://%s:%d/mcp", host, port)
            logger.info("Santé   : http://%s:%d/health", host, port)
            logger.info("PID     : %d", os.getpid())
            logger.info("Outils  : %s", ", ".join(t["name"] for t in TOOLS_METADATA))
            logger.info("=" * 60)
            server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur MCP...")
    except Exception as e:
        logger.error("Erreur lancement serveur HTTP : %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
