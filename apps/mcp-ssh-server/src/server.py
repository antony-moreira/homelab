import os
import json
import secrets
import datetime
from urllib.parse import parse_qs, urlencode
import docker as docker_sdk
import httpx
import paramiko
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
_auth_codes: dict = {}

SSH_USER = os.environ.get("SSH_USER", "antony")
SSH_HOST_HOMELAB = os.environ.get("SSH_HOST_HOMELAB", "192.168.3.110")

_SSH_HOSTS = {
    "homelab": (SSH_HOST_HOMELAB, SSH_USER),
    "leon": (os.environ.get("PROXMOX_LEON_IP", ""), "root"),
    "claire": (os.environ.get("PROXMOX_CLAIRE_IP", ""), "root"),
}


def _ssh_exec(host_alias: str, command: str, timeout: int = 30) -> str:
    if host_alias not in _SSH_HOSTS:
        return f"Host desconhecido: '{host_alias}'. Use: {', '.join(_SSH_HOSTS)}."
    hostname, username = _SSH_HOSTS[host_alias]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname, username=username,
            key_filename="/root/.ssh/id_rsa",
            timeout=10, banner_timeout=10,
        )
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        result = out if out else err
        return f"[exit {exit_code}]\n{result}" if result else f"[exit {exit_code}]"
    finally:
        client.close()


def _pve_get(base_url: str, path: str):
    r = httpx.get(
        f"{base_url}/{path}",
        headers={"Authorization": PROXMOX_AUTH},
        verify=False, timeout=10,
    )
    r.raise_for_status()
    return r.json()["data"]


def _pve_post(base_url: str, path: str, data: dict | None = None):
    r = httpx.post(
        f"{base_url}/{path}",
        headers={"Authorization": PROXMOX_AUTH},
        json=data or {},
        verify=False, timeout=10,
    )
    r.raise_for_status()
    return r.json().get("data")


def _pve_put(base_url: str, path: str, data: dict):
    r = httpx.put(
        f"{base_url}/{path}",
        headers={"Authorization": PROXMOX_AUTH},
        json=data,
        verify=False, timeout=10,
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


def _detect_kind(base_url: str, node: str, vmid: int) -> str:
    """Returns 'qemu' or 'lxc' for the given vmid."""
    for kind in ("qemu", "lxc"):
        try:
            _pve_get(base_url, f"nodes/{node}/{kind}/{vmid}/status/current")
            return kind
        except Exception:
            continue
    raise ValueError(f"VM/LXC {vmid} não encontrada em {node}.")


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


@mcp.tool()
def docker_logs_grep(container_name: str, pattern: str, lines: int = 200) -> str:
    """Busca padrão nos logs de um container. Útil para diagnosticar erros."""
    try:
        c = docker_client.containers.get(container_name)
        logs = c.logs(tail=lines).decode("utf-8", errors="replace")
        matches = [l for l in logs.splitlines() if pattern.lower() in l.lower()]
        return "\n".join(matches) if matches else f"Nenhuma ocorrência de '{pattern}'."
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


@mcp.tool()
def docker_container_stats(container_name: str) -> str:
    """Retorna uso atual de CPU e memória de um container Docker."""
    try:
        c = docker_client.containers.get(container_name)
        if c.status != "running":
            return f"Container '{container_name}' não está rodando ({c.status})."
        s = c.stats(stream=False)
        cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - s["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta = s["cpu_stats"]["system_cpu_usage"] - s["precpu_stats"]["system_cpu_usage"]
        num_cpus = s["cpu_stats"].get("online_cpus", 1)
        cpu_pct = round(cpu_delta / sys_delta * num_cpus * 100, 2) if sys_delta > 0 else 0
        mem_used = round(s["memory_stats"]["usage"] / 1024 ** 2, 1)
        mem_limit = round(s["memory_stats"]["limit"] / 1024 ** 2, 1)
        return f"{container_name} | CPU: {cpu_pct}% | RAM: {mem_used}/{mem_limit} MB"
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


@mcp.tool()
def docker_exec_command(container_name: str, command: str) -> str:
    """Executa comando shell dentro de um container Docker. Use para diagnóstico."""
    try:
        c = docker_client.containers.get(container_name)
        exit_code, output = c.exec_run(f"/bin/sh -c '{command}'", demux=False)
        result = output.decode("utf-8", errors="replace").strip() if output else ""
        return f"Exit {exit_code}:\n{result}" if result else f"Exit {exit_code}: (sem output)"
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


@mcp.tool()
def check_service_health(url: str) -> str:
    """Verifica se um serviço HTTP responde. Retorna status e tempo de resposta."""
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, verify=False)
        return f"{url} → {r.status_code} ({r.elapsed.total_seconds():.2f}s)"
    except httpx.TimeoutException:
        return f"{url} → TIMEOUT (>10s)"
    except Exception as e:
        return f"{url} → ERRO: {e}"


# ── SSH ───────────────────────────────────────────────────────────────────────

@mcp.tool()
def ssh_exec(host: str, command: str) -> str:
    """Executa comando SSH em um host. Hosts: homelab, leon, claire."""
    return _ssh_exec(host, command)


@mcp.tool()
def ssh_read_file(host: str, path: str) -> str:
    """Lê conteúdo de arquivo em host remoto via SSH. Hosts: homelab, leon, claire."""
    return _ssh_exec(host, f"cat {path}")


@mcp.tool()
def ssh_list_dir(host: str, path: str) -> str:
    """Lista arquivos em diretório remoto via SSH. Hosts: homelab, leon, claire."""
    return _ssh_exec(host, f"ls -la {path}")


# ── Docker extras ─────────────────────────────────────────────────────────────

@mcp.tool()
def docker_container_env(container_name: str) -> str:
    """Lista variáveis de ambiente de um container Docker."""
    try:
        info = docker_client.api.inspect_container(container_name)
        env_list = info["Config"].get("Env") or []
        return "\n".join(sorted(env_list)) if env_list else "Nenhuma variável encontrada."
    except docker_sdk.errors.NotFound:
        return f"Container '{container_name}' não encontrado."


@mcp.tool()
def traefik_list_routes() -> str:
    """Lista todas as rotas Traefik configuradas nos containers em execução."""
    containers = docker_client.containers.list()
    routes = []
    for c in containers:
        labels = c.labels
        if labels.get("traefik.enable", "").lower() != "true":
            continue
        for key, val in labels.items():
            if ".rule=" in key and "Host(" in val:
                router = key.split(".routers.")[1].split(".rule")[0] if ".routers." in key else "?"
                entrypoint = labels.get(
                    key.replace(".rule=", ".entrypoints=").replace(".rule", ".entrypoints"),
                    "?"
                )
                routes.append(f"{c.name:30} [{router}] {val} → {entrypoint}")
    return "\n".join(sorted(routes)) if routes else "Nenhuma rota encontrada."


# ── Proxmox — nodes ───────────────────────────────────────────────────────────

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
def proxmox_node_action(node: str, action: str) -> str:
    """Reinicia ou desliga um node Proxmox inteiro. Actions: reboot, shutdown."""
    valid = {"reboot", "shutdown"}
    if action not in valid:
        return f"Ação inválida: '{action}'. Use: {', '.join(valid)}."
    url = _node_url(node)
    _pve_post(url, f"nodes/{node}/status", {"command": action})
    return f"Node {node}: '{action}' enviado com sucesso."


# ── Proxmox — VMs/LXC ────────────────────────────────────────────────────────

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
    """Executa ação em uma VM ou LXC. Actions: start, stop, reboot, shutdown, suspend, resume."""
    valid = {"start", "stop", "reboot", "shutdown", "suspend", "resume"}
    if action not in valid:
        return f"Ação inválida: '{action}'. Use: {', '.join(valid)}."
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    _pve_post(url, f"nodes/{node}/{kind}/{vmid}/status/{action}")
    return f"{kind.upper()} {vmid} em {node}: '{action}' iniciado."


@mcp.tool()
def proxmox_vm_config(node: str, vmid: int) -> str:
    """Retorna configuração de uma VM/LXC: CPU, RAM, discos, rede."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    cfg = _pve_get(url, f"nodes/{node}/{kind}/{vmid}/config")
    lines = []
    for k, v in sorted(cfg.items()):
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


@mcp.tool()
def proxmox_vm_detach_disk(node: str, vmid: int, disk: str) -> str:
    """Desatacha um disco de uma VM (ex: disk='virtio0', 'scsi0'). Não deleta o storage."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    if kind != "qemu":
        return "Detach de disco só suportado em VMs QEMU, não LXC."
    _pve_post(url, f"nodes/{node}/{kind}/{vmid}/unlink", {"idlist": disk, "force": 0})
    return f"Disco '{disk}' desatachado de VM {vmid} em {node}. Storage preservado."


@mcp.tool()
def proxmox_vm_resize_disk(node: str, vmid: int, disk: str, size: str) -> str:
    """Expande disco de uma VM. size: ex '+10G' para adicionar 10GB, ou '50G' para total."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    _pve_put(url, f"nodes/{node}/{kind}/{vmid}/resize", {"disk": disk, "size": size})
    return f"Disco '{disk}' de VM {vmid} redimensionado para {size}."


@mcp.tool()
def proxmox_vm_snapshot(node: str, vmid: int, snapname: str, description: str = "") -> str:
    """Cria snapshot de uma VM/LXC."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    data = {"snapname": snapname}
    if description:
        data["description"] = description
    _pve_post(url, f"nodes/{node}/{kind}/{vmid}/snapshot", data)
    return f"Snapshot '{snapname}' criado para {kind.upper()} {vmid} em {node}."


@mcp.tool()
def proxmox_vm_list_snapshots(node: str, vmid: int) -> str:
    """Lista snapshots de uma VM/LXC."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    snaps = _pve_get(url, f"nodes/{node}/{kind}/{vmid}/snapshot")
    if not snaps:
        return "Nenhum snapshot encontrado."
    lines = []
    for s in snaps:
        ts = datetime.datetime.fromtimestamp(s["snaptime"]).strftime("%Y-%m-%d %H:%M") if s.get("snaptime") else "?"
        lines.append(f"{s['name']:30} {ts}  {s.get('description','')}")
    return "\n".join(lines)


@mcp.tool()
def proxmox_vm_rollback(node: str, vmid: int, snapname: str) -> str:
    """Faz rollback de uma VM/LXC para um snapshot. VM precisa estar desligada."""
    url = _node_url(node)
    kind = _detect_kind(url, node, vmid)
    _pve_post(url, f"nodes/{node}/{kind}/{vmid}/snapshot/{snapname}/rollback")
    return f"Rollback para snapshot '{snapname}' iniciado em {kind.upper()} {vmid}."


# ── Proxmox — storage/backup ──────────────────────────────────────────────────

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
def proxmox_list_all_backups() -> str:
    """Lista backups recentes de todas as VMs em ambos os nodes."""
    lines = []
    for node, url in (("leon", LEON_URL), ("claire", CLAIRE_URL)):
        try:
            tasks = _pve_get(url, f"nodes/{node}/tasks?typefilter=vzdump&limit=20")
            for t in tasks:
                start = datetime.datetime.fromtimestamp(t["starttime"]).strftime("%Y-%m-%d %H:%M")
                vmid = t.get("id", "?")
                status = t.get("status", "?")
                lines.append(f"{node:8} VM {vmid:>6}  {start}  {status}")
        except Exception as e:
            lines.append(f"{node}: erro ao consultar ({e})")
    return "\n".join(lines) if lines else "Nenhum backup encontrado."


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
    await send({
        "type": "http.response.start",
        "status": 302,
        "headers": [(b"location", location.encode()), (b"content-length", b"0")],
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
        cb = {"code": code}
        if state:
            cb["state"] = state
        await _send_redirect(scope, receive, send, f"{redirect_uri}?{urlencode(cb)}")
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

    # Bearer-protected MCP
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
