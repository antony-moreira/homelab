import os
import json
import secrets
import datetime
from urllib.parse import parse_qs, urlencode
import docker as docker_sdk
import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP

port = int(os.environ.get("MCP_PORT", 8765))
MCP_AUTH_TOKEN = os.environ["MCP_AUTH_TOKEN"]
MCP_PUBLIC_DOMAIN = os.environ.get("MCP_PUBLIC_DOMAIN", "")
BASE_URL = f"https://{MCP_PUBLIC_DOMAIN}" if MCP_PUBLIC_DOMAIN else ""

mcp = FastMCP("homelab", host="0.0.0.0", port=port)

PROXMOX_AUTH = f"PVEAPIToken=root@pam!homepage={os.environ['PROXMOX_TOKEN_SECRET']}"
LEON_URL = f"https://{os.environ['PROXMOX_LEON_IP']}:8006/api2/json"
CLAIRE_URL = f"https://{os.environ['PROXMOX_CLAIRE_IP']}:8006/api2/json"

docker_client = docker_sdk.from_env()

# in-memory auth codes: {code: {"redirect_uri": ..., "expires": ...}}
_auth_codes: dict = {}


def _pve_get(base_url: str, path: str):
    r = httpx.get(
        f"{base_url}/{path}",
        headers={"Authorization": PROXMOX_AUTH},
        verify=False,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["data"]


def _pve_post(base_url: str, path: str):
    r = httpx.post(
        f"{base_url}/{path}",
        headers={"Authorization": PROXMOX_AUTH},
        verify=False,
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data")


def _node_url(node: str) -> str:
    n = node.lower()
    if n == "leon":
        return LEON_URL
    if n == "claire":
        return CLAIRE_URL
    raise ValueError(f"Node desconhecido: '{node}'. Use 'leon' ou 'claire'.")


# ── Docker ────────────────────────────────────────────────────────────────────

@mcp.tool()
def docker_list_containers() -> str:
    """Lista todos os containers Docker com nome, status e imagem."""
    containers = docker_client.containers.list(all=True)
    if not containers:
        return "Nenhum container encontrado."
    lines = []
    for c in containers:
        image = c.image.tags[0] if c.image.tags else "unknown"
        lines.append(f"{c.name}: {c.status} | {image}")
    return "\n".join(lines)


@mcp.tool()
def docker_container_action(container_name: str, action: str) -> str:
    """Executa ação em um container Docker. Ações: start, stop, restart."""
    valid = {"start", "stop", "restart"}
    if action not in valid:
        return f"Ação inválida: '{action}'. Use: {', '.join(valid)}."
    try:
        c = docker_client.containers.get(container_name)
        getattr(c, action)()
        return f"Container '{container_name}': {action} executado com sucesso."
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


@mcp.tool()
def docker_container_logs(container_name: str, lines: int = 50) -> str:
    """Retorna as últimas N linhas de log de um container Docker."""
    try:
        c = docker_client.containers.get(container_name)
        logs = c.logs(tail=lines).decode("utf-8", errors="replace")
        return logs.strip() if logs.strip() else "Sem logs disponíveis."
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


# ── Proxmox ───────────────────────────────────────────────────────────────────

@mcp.tool()
def proxmox_node_status(node: str) -> str:
    """Status de CPU, RAM e uptime de um node Proxmox. Node: leon ou claire."""
    url = _node_url(node)
    d = _pve_get(url, f"nodes/{node}/status")
    cpu = round(d["cpu"] * 100, 1)
    mem_used = round(d["memory"]["used"] / 1024 ** 3, 1)
    mem_total = round(d["memory"]["total"] / 1024 ** 3, 1)
    hours = d["uptime"] // 3600
    return f"Node {node} | CPU: {cpu}% | RAM: {mem_used}/{mem_total} GB | Uptime: {hours}h"


@mcp.tool()
def proxmox_list_vms(node: str) -> str:
    """Lista VMs e containers LXC em um node Proxmox. Node: leon ou claire."""
    url = _node_url(node)
    vms = _pve_get(url, f"nodes/{node}/qemu")
    lxcs = _pve_get(url, f"nodes/{node}/lxc")
    lines = []
    for v in sorted(vms, key=lambda x: x["vmid"]):
        lines.append(f"VM  {v['vmid']:>4} ({v.get('name','?'):20}): {v['status']}")
    for l in sorted(lxcs, key=lambda x: x["vmid"]):
        lines.append(f"LXC {l['vmid']:>4} ({l.get('name','?'):20}): {l['status']}")
    return "\n".join(lines) if lines else "Nenhuma VM encontrada."


@mcp.tool()
def proxmox_vm_action(node: str, vmid: int, action: str) -> str:
    """Executa ação em uma VM ou LXC. Actions: start, stop, reboot, shutdown."""
    valid = {"start", "stop", "reboot", "shutdown"}
    if action not in valid:
        return f"Ação inválida: '{action}'. Use: {', '.join(valid)}."
    url = _node_url(node)
    for kind in ("qemu", "lxc"):
        try:
            _pve_post(url, f"nodes/{node}/{kind}/{vmid}/status/{action}")
            return f"{kind.upper()} {vmid} em {node}: '{action}' iniciado."
        except Exception:
            continue
    return f"VM/LXC {vmid} não encontrada em {node}."


@mcp.tool()
def proxmox_backup_status(vmid: int) -> str:
    """Verifica histórico dos últimos backups de uma VM."""
    tasks = _pve_get(LEON_URL, f"nodes/leon/tasks?vmid={vmid}&typefilter=vzdump&limit=5")
    if not tasks:
        return "Nenhum backup encontrado."
    lines = []
    for t in tasks:
        start = datetime.datetime.fromtimestamp(t["starttime"]).strftime("%Y-%m-%d %H:%M")
        lines.append(f"{start}: {t.get('status', '?')}")
    return "\n".join(lines)


@mcp.tool()
def proxmox_storage_status(node: str) -> str:
    """Verifica uso de storage em um node Proxmox. Node: leon ou claire."""
    url = _node_url(node)
    storages = _pve_get(url, f"nodes/{node}/storage")
    lines = []
    for s in storages:
        if not s.get("active"):
            continue
        used = round(s.get("used", 0) / 1024 ** 3, 1)
        total = round(s.get("total", 1) / 1024 ** 3, 1)
        pct = round(s.get("used", 0) / max(s.get("total", 1), 1) * 100)
        lines.append(f"{s['storage']:25} {used:>6}/{total:>6} GB ({pct}%)")
    return "\n".join(lines) if lines else "Sem informação de storage."


# ── ASGI helpers ──────────────────────────────────────────────────────────────

async def _send_json(scope, receive, send, data: dict, status: int = 200):
    body = json.dumps(data).encode()
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


async def _send_redirect(scope, receive, send, location: str):
    loc = location.encode()
    await send({
        "type": "http.response.start",
        "status": 302,
        "headers": [
            (b"location", loc),
            (b"content-length", b"0"),
        ],
    })
    await send({"type": "http.response.body", "body": b""})


async def _read_body(receive) -> bytes:
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    return body


# ── OAuth 2.0 Authorization Code + PKCE ──────────────────────────────────────

OPEN_PATHS = {
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
    "/token",
    "/authorize",
}

OAUTH_META = {
    "issuer": BASE_URL,
    "authorization_endpoint": f"{BASE_URL}/authorize",
    "token_endpoint": f"{BASE_URL}/token",
    "response_types_supported": ["code"],
    "grant_types_supported": ["authorization_code", "client_credentials"],
    "code_challenge_methods_supported": ["S256"],
    "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
}


mcp_app = mcp.streamable_http_app()


async def app(scope, receive, send):
    if scope["type"] == "lifespan":
        await mcp_app(scope, receive, send)
        return

    if scope["type"] != "http":
        await mcp_app(scope, receive, send)
        return

    path = scope.get("path", "")
    query = scope.get("query_string", b"").decode()

    # ── public OAuth endpoints ────────────────────────────────────────────────

    if path == "/.well-known/oauth-protected-resource":
        await _send_json(scope, receive, send, {
            "resource": BASE_URL,
            "authorization_servers": [BASE_URL],
        })
        return

    if path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
        await _send_json(scope, receive, send, OAUTH_META)
        return

    if path == "/authorize":
        params = {k: v[0] for k, v in parse_qs(query).items()}
        redirect_uri = params.get("redirect_uri", "")
        state = params.get("state", "")
        code = secrets.token_urlsafe(32)
        _auth_codes[code] = {
            "redirect_uri": redirect_uri,
            "expires": datetime.datetime.utcnow() + datetime.timedelta(seconds=120),
        }
        callback_params = {"code": code}
        if state:
            callback_params["state"] = state
        await _send_redirect(scope, receive, send, f"{redirect_uri}?{urlencode(callback_params)}")
        return

    if path == "/token":
        body = await _read_body(receive)
        params = {k: v[0] for k, v in parse_qs(body.decode()).items()}
        grant_type = params.get("grant_type", "")

        if grant_type == "authorization_code":
            code = params.get("code", "")
            entry = _auth_codes.pop(code, None)
            if entry and datetime.datetime.utcnow() < entry["expires"]:
                await _send_json(scope, receive, send, {
                    "access_token": MCP_AUTH_TOKEN,
                    "token_type": "bearer",
                    "expires_in": 86400,
                })
            else:
                await _send_json(scope, receive, send, {"error": "invalid_grant"}, status=400)
        elif grant_type == "client_credentials":
            if params.get("client_secret") == MCP_AUTH_TOKEN:
                await _send_json(scope, receive, send, {
                    "access_token": MCP_AUTH_TOKEN,
                    "token_type": "bearer",
                    "expires_in": 86400,
                })
            else:
                await _send_json(scope, receive, send, {"error": "invalid_client"}, status=401)
        else:
            await _send_json(scope, receive, send, {"error": "unsupported_grant_type"}, status=400)
        return

    # ── Bearer-protected MCP ──────────────────────────────────────────────────

    headers = dict(scope.get("headers", []))
    auth = headers.get(b"authorization", b"").decode()
    if not (auth.startswith("Bearer ") and auth[7:] == MCP_AUTH_TOKEN):
        www_auth = (
            f'Bearer realm="homelab",'
            f' resource_metadata="{BASE_URL}/.well-known/oauth-protected-resource"'
        ).encode()
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"text/plain"),
                (b"content-length", b"12"),
                (b"www-authenticate", www_auth),
            ],
        })
        await send({"type": "http.response.body", "body": b"Unauthorized"})
        return

    await mcp_app(scope, receive, send)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
