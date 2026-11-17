#!/data/data/com.termux/files/usr/bin/env bash
# Script pour arrêter le serveur MCP autonome

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"

if [ ! -f "$PID_FILE" ]; then
    # Vérification si un processus python3 mcp_server.py tourne quand même
    PIDS=$(pgrep -f "python3.*mcp_server.py" 2>/dev/null)
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

PID=$(cat "$PID_FILE")
if [ -z "$PID" ]; then
    rm -f "$PID_FILE"
    echo "[INFO] Fichier PID vide supprimé."
    exit 0
fi

if kill -0 "$PID" 2>/dev/null; then
    echo "[INFO] Arrêt du serveur MCP (PID : $PID)..."
    kill "$PID" 2>/dev/null

    # Attente de l'arrêt
    for i in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 0.2
    done

    # Si toujours vivant, forcer avec SIGKILL
    if kill -0 "$PID" 2>/dev/null; then
        echo "[INFO] Forçage de l'arrêt..."
        kill -9 "$PID" 2>/dev/null
    fi

    rm -f "$PID_FILE"
    echo "[OK] Serveur MCP arrêté."
else
    echo "[INFO] Le processus $PID n'est plus actif."
    rm -f "$PID_FILE"
fi
