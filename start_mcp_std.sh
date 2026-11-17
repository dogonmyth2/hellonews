#!/usr/bin/env bash
# Script pour démarrer le serveur MCP autonome en tâche de fond indépendante

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"
LOG_FILE="$SCRIPT_DIR/mcp_server.log"
SERVER_SCRIPT="$SCRIPT_DIR/mcp_server.py"
PORT=8765

resolve_python() {
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >/dev/null 2>&1; then
                echo "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

check_health() {
    local url="http://127.0.0.1:$PORT/health"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS "$url" 2>/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$url" 2>/dev/null
    else
        "$PYTHON_BIN" -c "import urllib.request; print(urllib.request.urlopen('$url', timeout=2).read().decode())" 2>/dev/null
    fi
}

if [ ! -f "$SERVER_SCRIPT" ]; then
    echo "[ERREUR] Script serveur introuvable : $SERVER_SCRIPT" >&2
    exit 1
fi

PYTHON_BIN="$(resolve_python)" || {
    echo "[ERREUR] Python 3 est introuvable ou non fonctionnel dans le PATH." >&2
    exit 1
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

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if is_pid_running "$PID"; then
        echo "[INFO] Le serveur MCP est déjà en cours d'exécution (PID : $PID, Port : $PORT)."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

echo "[INFO] Démarrage du serveur MCP autonome..."
if "$PYTHON_BIN" -c "import os, sys; sys.exit(0 if hasattr(os, 'fork') else 1)" >/dev/null 2>&1; then
    "$PYTHON_BIN" "$SERVER_SCRIPT" --daemon --pidfile "$PID_FILE" --logfile "$LOG_FILE" --host 127.0.0.1 --port "$PORT"
    START_RC=$?
else
    "$PYTHON_BIN" -c "
import subprocess, sys
server, pidfile, logfile, port = sys.argv[1:5]
flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
with open(logfile, 'a', encoding='utf-8') as lf:
    subprocess.Popen(
        [sys.executable, server, '--pidfile', pidfile, '--host', '127.0.0.1', '--port', port],
        stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
        creationflags=flags, close_fds=True
    )
" "$SERVER_SCRIPT" "$PID_FILE" "$LOG_FILE" "$PORT"
    START_RC=$?
fi
if [ "$START_RC" -ne 0 ]; then
    echo "[ERREUR] Échec du lancement ($PYTHON_BIN, code $START_RC). Consultez $LOG_FILE :" >&2
    tail -n 20 "$LOG_FILE" 2>/dev/null
    exit "$START_RC"
fi

# Attente et vérification de la disponibilité
READY=0
for _ in {1..15}; do
    sleep 0.2
    STATUS=$(check_health)
    if [ -n "$STATUS" ]; then
        READY=1
        break
    fi
done

if [ "$READY" -eq 1 ] && [ -f "$PID_FILE" ]; then
    SERVER_PID=$(cat "$PID_FILE")
    echo "============================================================"
    echo "  Serveur MCP autonome démarré avec succès !"
    echo "============================================================"
    echo "  PID         : $SERVER_PID"
    echo "  URL Endpoint: http://127.0.0.1:$PORT/mcp"
    echo "  Health Check: http://127.0.0.1:$PORT/health"
    echo "  Fichier Log : $LOG_FILE"
    echo "============================================================"
else
    echo "[ERREUR] Échec du démarrage du serveur. Consultez $LOG_FILE :" >&2
    tail -n 20 "$LOG_FILE" 2>/dev/null
    exit 1
fi
