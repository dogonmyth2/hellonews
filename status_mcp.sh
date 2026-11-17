#!/data/data/com.termux/files/usr/bin/env bash
# Script pour vérifier l'état du serveur MCP autonome

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"
PORT=8765

echo "=== État du serveur MCP autonome ==="
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[STATUS] En cours d'exécution (PID : $PID)"
        echo "Test de l'endpoint de santé (http://127.0.0.1:$PORT/health) :"
        curl -s "http://127.0.0.1:$PORT/health" || echo "[ERREUR] Le serveur ne répond pas sur le port $PORT."
        echo ""
    else
        echo "[STATUS] Inactif (Fichier PID orphelin : $PID)"
    fi
else
    echo "[STATUS] Inactif (aucun processus démarré)"
fi
