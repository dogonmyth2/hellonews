# Serveur MCP Autonome (`mcp_server.py`)

Ce composant fournit un serveur standard **Model Context Protocol (MCP)**, exécutable de manière indépendante en tâche de fond (démon HTTP) ou en mode interactif Stdio.

Il est conçu pour être lancé par l'utilisateur comme une **tâche séparée** et permet à des assistants IA (Google Antigravity, Claude Desktop, clients MCP personnalisés) de consommer dynamiquement ses outils.

---

## 1. Caractéristiques techniques

* **Zéro dépendance externe** : Conçu 100% en Python 3 natif (modules `http.server`, `json`, `urllib`, `threading`, `socketserver`).
* **Double transport MCP supporté** :
  1. **Streamable HTTP (Recommandé pour tâche autonome)** : Écoute locale sur `http://127.0.0.1:8765/mcp`.
  2. **Stdio** : Exécution directe en pipeline via `python3 mcp_server.py --stdio`.
* **Supervision intégrée** : Endpoint de diagnostic et santé `GET /health`, gestion de PID et journalisation des logs.

---

## 2. Outils exposés au modèle IA

| Nom de l'outil | Description | Paramètres |
| :--- | :--- | :--- |
| `get_weather` | Météo en direct (température, ressenti, conditions WMO, humidité) via Open-Meteo & géolocalisation IP. | `city` *(string, optionnel)* : Nom d'une ville (ex: `Paris`, `Lyon`). Si omis, utilise la position actuelle de la machine. |
| `get_stock_quote` | Cours de bourse en direct et variations quotidienne absolue et en pourcentage via Yahoo Finance. | `symbol` *(string, requis)* : Ticker boursier (ex: `GLE.PA`, `AIR.PA`, `AI.PA`, `AAPL`). |
| `get_news` | Top articles d'actualités par mot-clé thématique ou pour la France via Google News RSS. | • `topic` *(string, défaut: "agentic AI")*<br>• `count` *(integer, défaut: 5)* |
| `get_system_info` | Informations d'exécution du système hôte (OS, architecture processeur, version Python, PID, Uptime). | *Aucun* |

---

## 3. Gestion du cycle de vie (Démarrage, Arrêt, Statut)

Trois scripts automatisés sont à votre disposition :

### Démarrer le serveur en tâche de fond
```bash
./start_mcp.sh
```
*Le serveur est lancé en arrière-plan, son PID est enregistré dans `mcp_server.pid` et les journaux sont redirigés dans `mcp_server.log`.*

### Vérifier le statut et la santé
```bash
./status_mcp.sh
```
Ou directement avec curl :
```bash
curl -s http://127.0.0.1:8765/health
```

### Arrêter le serveur
```bash
./stop_mcp.sh
```

---

## 4. Validation avec le client de test automatisé

Un client simulant les échanges JSON-RPC 2.0 d'un assistant IA complet est inclus :

```bash
./test_mcp_client.py
```

Le script valide successivement :
1. La négociation initiale du protocole (`initialize`).
2. L'accusé de réception (`notifications/initialized`).
3. L'inventaire des outils (`tools/list`).
4. L'appel et l'exécution unitaire de chaque outil (`tools/call`).

---

## 5. Configuration avec Google Antigravity

Pour connecter Antigravity à ce serveur MCP autonome :

### Option 1 : Configuration globale
Ajoutez la déclaration dans `~/.gemini/config/mcp_config.json` :
```json
{
  "mcpServers": {
    "standalone-tools": {
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

### Option 2 : Mode Stdio direct (sans serveur HTTP de fond)
Si vous préférez qu'Antigravity lance le script automatiquement à chaque session :
```json
{
  "mcpServers": {
    "standalone-tools": {
      "command": "python3",
      "args": ["/data/data/com.termux/files/home/testagy/mcp_server.py", "--stdio"]
    }
  }
}
```
