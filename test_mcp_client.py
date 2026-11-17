#!/data/data/com.termux/files/usr/bin/env python3
"""Automated Test Client for Standalone MCP Server.

Validates the full MCP JSON-RPC 2.0 lifecycle:
1. initialize
2. notifications/initialized
3. tools/list
4. tools/call for all tools
"""

import json
import sys
import urllib.error
import urllib.request

MCP_URL = "http://127.0.0.1:8765/mcp"


def send_mcp_request(method: str, params: dict | None = None, req_id: int | None = 1) -> dict | None:
    """Send JSON-RPC request to the MCP server."""
    payload = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        payload["id"] = req_id
    if params is not None:
        payload["params"] = params

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "MCP-Test-Client/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            if resp.status == 204:
                return None
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        print(f"[HTTP ERROR {e.code}] {e.read().decode('utf-8')}")
        raise
    except Exception as e:
        print(f"[COMMUNICATION ERROR] {e}")
        raise


def run_tests():
    print("=" * 65)
    print("  Démarrage des tests du client MCP (http://127.0.0.1:8765/mcp)")
    print("=" * 65)

    # 1. Test initialize
    print("\n[1/4] Test de la méthode 'initialize'...")
    init_resp = send_mcp_request(
        "initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
        req_id=1,
    )
    assert init_resp is not None, "La réponse initialize ne doit pas être vide"
    res = init_resp.get("result", {})
    server_info = res.get("serverInfo", {})
    proto_ver = res.get("protocolVersion")
    print(f"  ✓ Serveur : {server_info.get('name')} v{server_info.get('version')}")
    print(f"  ✓ Version protocole : {proto_ver}")

    # 2. Test notification initialized
    print("\n[2/4] Test de la notification 'notifications/initialized'...")
    notif_resp = send_mcp_request("notifications/initialized", req_id=None)
    assert notif_resp is None, "Une notification ne doit pas renvoyer de corps"
    print("  ✓ Notification acceptée (HTTP 204 No Content)")

    # 3. Test tools/list
    print("\n[3/4] Test de la méthode 'tools/list'...")
    tools_resp = send_mcp_request("tools/list", req_id=2)
    assert tools_resp is not None
    tools = tools_resp.get("result", {}).get("tools", [])
    assert len(tools) >= 4, f"Au moins 4 outils attendus, reçu {len(tools)}"
    print(f"  ✓ Outils découverts ({len(tools)}) :")
    for t in tools:
        print(f"    • {t['name']} : {t['description'][:60]}...")

    # 4. Test tools/call for each tool
    print("\n[4/4] Test de l'exécution de chaque outil via 'tools/call'...")

    # 4a. get_weather
    print("\n  -> Test de 'get_weather' (Paris) :")
    w_resp = send_mcp_request(
        "tools/call",
        params={"name": "get_weather", "arguments": {"city": "Paris"}},
        req_id=3,
    )
    w_text = w_resp["result"]["content"][0]["text"]
    print(f"     Résultat : {w_text}")
    assert "Météo à Paris" in w_text or "°C" in w_text

    # 4b. get_stock_quote
    print("\n  -> Test de 'get_stock_quote' (AIR.PA) :")
    s_resp = send_mcp_request(
        "tools/call",
        params={"name": "get_stock_quote", "arguments": {"symbol": "AIR.PA"}},
        req_id=4,
    )
    s_text = s_resp["result"]["content"][0]["text"]
    print(f"     Résultat : {s_text}")
    assert "AIR.PA" in s_text

    # 4c. get_news
    print("\n  -> Test de 'get_news' (agentic AI) :")
    n_resp = send_mcp_request(
        "tools/call",
        params={"name": "get_news", "arguments": {"topic": "agentic AI", "count": 2}},
        req_id=5,
    )
    n_text = n_resp["result"]["content"][0]["text"]
    print(f"     Résultat :\n{n_text}")
    assert "Top" in n_text

    # 4d. get_system_info
    print("\n  -> Test de 'get_system_info' :")
    sys_resp = send_mcp_request(
        "tools/call",
        params={"name": "get_system_info", "arguments": {}},
        req_id=6,
    )
    sys_text = sys_resp["result"]["content"][0]["text"]
    print(f"     Résultat :\n{sys_text}")
    assert "Système" in sys_text

    print("\n" + "=" * 65)
    print("  TOUS LES TESTS MCP SONT VALIDÉS AVEC SUCCÈS (100% OK)")
    print("=" * 65)


if __name__ == "__main__":
    try:
        run_tests()
    except Exception as e:
        print(f"\n[ÉCHEC DES TESTS] : {e}")
        sys.exit(1)
