#!/usr/bin/env bash
# Script pour arrêter le serveur MCP autonome

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"

if [ ! -f "$PID_FILE" ]; then
    # Vérification si un processus python/python3 mcp_server.py tourne quand même
    PIDS=""
    if command -v pgrep >/dev/null 2>&1; then
        PIDS=$(pgrep -f "python3?.*mcp_server\.py" 2>/dev/null)
    fi
    if [ -n "$PIDS" ]; then
        echo "[INFO] Aucun fichier PID trouvé mais processus détecté ($PIDS). Arrêt en cours..."
        kill $PIDS 2>/dev/null
        echo "[OK] Processus arrêté."
        exit 0
    else
        echo "[INFO] Aucun serveur MCP n'est en cours d'exécution."
        exit 0
    fi
fi

PID=$(cat "$PID_FILE" 2>/dev/null)
if [ -z "$PID" ]; then
    rm -f "$PID_FILE"
    echo "[INFO] Fichier PID vide supprimé."
    exit 0
fi

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

if is_pid_running "$PID"; then
    echo "[INFO] Arrêt du serveur MCP (PID : $PID)..."
    if kill "$PID" 2>/dev/null; then
        # Attente de l'arrêt
        for _ in {1..10}; do
            if ! is_pid_running "$PID"; then
                break
            fi
            sleep 0.2
        done

        # Si toujours vivant, forcer avec SIGKILL
        if is_pid_running "$PID"; then
            echo "[INFO] Forçage de l'arrêt..."
            kill -9 "$PID" 2>/dev/null
        fi
    elif command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "Stop-Process -Id $PID -Force -ErrorAction SilentlyContinue" >/dev/null 2>&1
    fi

    rm -f "$PID_FILE"
    echo "[OK] Serveur MCP arrêté."
else
    echo "[INFO] Le processus $PID n'est plus actif."
    rm -f "$PID_FILE"
fi
