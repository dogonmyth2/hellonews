#!/usr/bin/env bash
# Script pour vérifier l'état du serveur MCP autonome

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"
PORT=8765

check_health() {
    local url="http://127.0.0.1:$PORT/health"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "$url"
        return $?
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$url"
        return $?
    fi
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >/dev/null 2>&1; then
            "$candidate" -c "import urllib.request; print(urllib.request.urlopen('$url', timeout=2).read().decode(), end='')" 2>/dev/null
            return $?
        fi
    done
    return 1
}

is_pid_running() {
    local pid="$1"
    [ -n "$pid" ] || return 1
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    fi
    if command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "Get-Process -Id $pid -ErrorAction Stop | Out-Null" >/dev/null 2>&1
        return $?
    fi
    return 1
}

echo "=== État du serveur MCP autonome ==="
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if is_pid_running "$PID"; then
        echo "[STATUS] En cours d'exécution (PID : $PID)"
        echo "Test de l'endpoint de santé (http://127.0.0.1:$PORT/health) :"
        check_health || echo "[ERREUR] Le serveur ne répond pas sur le port $PORT."
        echo ""
    else
        echo "[STATUS] Inactif (Fichier PID orphelin : ${PID:-vide})"
    fi
else
    echo "[STATUS] Inactif (aucun processus démarré)"
fi
