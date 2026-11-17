#!/data/data/com.termux/files/usr/bin/env bash
# Script pour démarrer le serveur MCP autonome en tâche de fond indépendante

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"
LOG_FILE="$SCRIPT_DIR/mcp_server.log"
PORT=8765

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "[INFO] Le serveur MCP est déjà en cours d'exécution (PID : $PID, Port : $PORT)."
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

echo "[INFO] Démarrage du serveur MCP autonome..."
python3 "$SCRIPT_DIR/mcp_server.py" --daemon --pidfile "$PID_FILE" --logfile "$LOG_FILE" --host 127.0.0.1 --port "$PORT"

# Attente et vérification de la disponibilité
READY=0
for i in {1..15}; do
    sleep 0.2
    STATUS=$(curl -s "http://127.0.0.1:$PORT/health" 2>/dev/null)
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
    echo "[ERREUR] Échec du démarrage du serveur. Consultez $LOG_FILE :"
    tail -n 20 "$LOG_FILE" 2>/dev/null
    exit 1
fi
