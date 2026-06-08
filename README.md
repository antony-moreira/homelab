# Homelab

Documentação completa da infraestrutura, stacks Docker e procedimentos do homelab.

---

## Índice

- [Arquitetura](#arquitetura)
- [Hardware e Infraestrutura](#hardware-e-infraestrutura)
- [Rede](#rede)
- [Pré-requisitos](#pré-requisitos)
- [Instalação Base](#instalação-base)
- [Traefik](#traefik)
- [Dockhand](#dockhand)
- [Apps Docker](#apps-docker)
  - [Dashboard](#dashboard-homepage--dashdot)
  - [Arrs Stack](#arrs-stack-media)
  - [Jellyfin](#jellyfin)
  - [Plex](#plex)
  - [Monitoring Stack](#monitoring-stack-netdata--prometheus--grafana)
  - [Nextcloud](#nextcloud)
  - [Syncthing](#syncthing)
  - [Filebrowser](#filebrowser)
  - [Uptime Kuma](#uptime-kuma)
  - [Heimdall](#heimdall)
  - [AdGuard Home Sync](#adguard-home-sync)
  - [Time Machine](#time-machine)
  - [Tailscale](#tailscale)
  - [Watchtower](#watchtower)
- [Containers LXC](#containers-lxc)
- [MCP SSH Server](#mcp-ssh-server)
- [Scripts de Manutenção](#scripts-de-manutenção)
- [Proxmox Leon — Configurações Específicas](#proxmox-leon--configurações-específicas)
- [Acesso Externo](#acesso-externo)

---

## Arquitetura

```
Internet
    │
Cloudflare DNS + Tunnel
    │
    ├── Traefik (reverse proxy, porta 443)
    │       └── Docker containers via labels
    │       └── LXC / VMs via dynamic.yml
    │
    ├── Tailscale (VPN mesh, sub-rede local)
    │
Servidor Principal
    │
    ├── Proxmox Leon
    │       └── VMs e guests
    │
    └── Proxmox Claire (sempre ligado)
            └── LXC AdGuard Secondary
            └── LXC Tailscale
            └── LXC UPSnap (Wake on LAN)
```

---

## Hardware e Infraestrutura

| Dispositivo | Variável | Função |
|---|---|---|
| Servidor principal | `SERVER_IP` | Roda todos os containers Docker |
| Proxmox Leon | `PROXMOX_LEON_IP` | Hypervisor principal |
| Proxmox Claire | `PROXMOX_CLAIRE_IP` | Hypervisor secundário / sempre ligado |
| AdGuard Primary | `ADGUARD_IP` | DNS primário da rede |
| AdGuard Secondary | `ADGUARD_SECONDARY_IP` | DNS secundário (LXC no Claire) |
| UPSnap | `UPSNAP_IP` | Wake on LAN (LXC no Claire) |

Todos os IPs são definidos nos arquivos `.env` de cada stack (ver `.env.example`).

### Proxmox API Token

Usado por Homepage e MCP Server para consultar status dos nodes/VMs:

```
PVEAPIToken=root@pam!<TOKEN_NAME>=<TOKEN_SECRET>
```

Gerar em: Proxmox → Datacenter → API Tokens.

---

## Rede

### Convenção de domínios

Dois tipos de acesso:

| Sufixo | Acesso | Como funciona |
|---|---|---|
| `*.seudominio.com` | Público via Cloudflare Tunnel | Cloudflare → Traefik porta 8080 |
| `*.home.seudominio.com` | Local via Tailscale/rede interna | DNS resolve direto → Traefik porta 443 |

### Cloudflare Tunnel

O container `cloudflared` cria um túnel permanente para o Cloudflare. O Traefik tem um entrypoint `tunnel` na porta `8080` para receber esse tráfego.

Configurado em `apps/traefik/cloudflared-config.yml`.

### AdGuard Home Sync

Sincroniza configurações do AdGuard primário para o secundário a cada hora. Configurado em `apps/adguardhome-sync/adguardhome-sync.yaml` (baseado no `.yaml.example`).

---

## Pré-requisitos

No servidor principal:

- Docker Engine + Docker Compose plugin
- Usuário com acesso ao Docker (`usermod -aG docker <user>`)
- SSH key configurada (`~/.ssh/`) e distribuída para os nodes Proxmox
- Rede Docker externa criada:

```bash
docker network create traefik
```

- Arquivo `acme.json` com permissão correta:

```bash
touch /home/<user>/apps/traefik/acme.json
chmod 600 /home/<user>/apps/traefik/acme.json
```

---

## Instalação Base

### Estrutura de diretórios no servidor

```
/home/<user>/apps/
├── traefik/
├── dockhand/
├── adguardhome-sync/
├── arrs-stack/          # homarr, overseerr, prowlarr, radarr, sonarr, bazarr, qbittorrent
├── dashboard/           # homepage, dashdot
├── jellyfin/
├── plex/
├── nextcloud/           # nextcloud + nextcloud-db (MariaDB)
├── monitoring-stack/    # netdata, node-exporter, prometheus, grafana
├── syncthing/
├── filebrowser/
├── uptime-kuma/
├── heimdall/
├── tailscale/
├── watchtower/
├── time-machine/
└── mcp-ssh-server/
```

### Fluxo de deploy com Dockhand

1. Editar arquivos no repo local
2. Fazer `git push`
3. Dockhand detecta mudança no branch e atualiza o stack automaticamente
4. Para stacks com arquivos de volume fora do compose (ex: `dynamic.yml` do Traefik), copiar manualmente para `/home/<user>/apps/<stack>/`

> **Importante:** Dockhand sobrescreve o `.env` com `.env.dockhand` gerenciado pela sua UI. Vars de ambiente novas devem ser adicionadas tanto no `docker-compose.yaml` (seção `environment`) quanto na UI do Dockhand.

---

## Traefik

**Imagem:** `traefik:v3`  
**Arquivo principal:** `apps/traefik/traefik.yml`  
**Roteamento dinâmico:** `apps/traefik/dynamic.yml`

### Entrypoints

| Nome | Porta | Uso |
|---|---|---|
| `web` | `80` | Redireciona para `websecure` |
| `websecure` | `443` | HTTPS principal (local + Tailscale) |
| `tunnel` | `8080` | Cloudflare Tunnel |

### Certificados

Gerados automaticamente via DNS Challenge com Cloudflare (`CF_DNS_API_TOKEN`). Armazenados em `acme.json`.

### Configuração manual pós-deploy

1. Copiar `dynamic.yml` para `/home/<user>/apps/traefik/dynamic.yml` se alterado
2. Traefik recarrega automaticamente (`watch: true`) — não precisa de restart para mudanças no `dynamic.yml`
3. Para mudanças no `.env` ou `docker-compose.yaml`: force-recreate necessário

```bash
cd /home/<user>/apps/dockhand/dockhand_data/stacks/<repo>/traefik
docker compose --env-file .env.dockhand up -d --force-recreate
```

### Serviços roteados via dynamic.yml (sem Docker labels)

| Serviço | Domínio (var) | Backend |
|---|---|---|
| Proxmox Leon | `PROXMOX_LEON_HOME_DOMAIN` | `https://<PROXMOX_LEON_IP>:8006` |
| Proxmox Claire | `PROXMOX_CLAIRE_HOME_DOMAIN` | `https://<PROXMOX_CLAIRE_IP>:8006` |
| AdGuard Primary | `ADGUARD_HOME_DOMAIN` | `http://<ADGUARD_IP>:<ADGUARD_PORT>` |
| AdGuard Secondary | `ADGUARD_SECONDARY_HOME_DOMAIN` | `http://<ADGUARD_SECONDARY_IP>:<ADGUARD_PORT>` |
| Plex | `PLEX_HOME_DOMAIN` | `http://<SERVER_IP>:32400` |
| UPSnap | `UPSNAP_HOME_DOMAIN` | `http://<UPSNAP_IP>:8090` |

> Proxmox usa `serversTransport: insecure` (skip TLS verify) pois o certificado é self-signed.

### Adicionar novo serviço LXC/VM ao Traefik

1. Adicionar router e service no `dynamic.yml`
2. Adicionar `NOVO_DOMAIN` e `NOVO_IP` no `docker-compose.yaml` do Traefik (seção `environment`)
3. Adicionar as vars no `.env.example` e na UI do Dockhand
4. Copiar `dynamic.yml` atualizado para o servidor
5. Force-recreate do Traefik para carregar as novas vars

---

## Dockhand

**Imagem:** `fnsys/dockhand:latest`  
**Porta:** `3000`  
**URL:** `dockhand.home.seudominio.com`

Gerencia stacks Docker a partir de um repositório Git. Monitora branches e faz redeploy automático quando detecta mudanças.

### Configuração inicial

1. Acessar `http://<server-ip>:3000`
2. Criar conta admin
3. Adicionar repositório Git (HTTPS ou SSH)
4. Para cada stack: adicionar as variáveis de ambiente na aba "Environment"
5. Dockhand cria o arquivo `.env.dockhand` no diretório do stack

### Adicionar variável nova a um stack existente

1. No `docker-compose.yaml` do stack, adicionar a var na seção `environment`
2. Commitar e fazer push
3. Na UI do Dockhand, ir no stack → "Environment" → adicionar a var com o valor real
4. Dockhand fará redeploy automático (ou clicar em "Deploy")

> Dockhand **não** usa o `.env` do repo — apenas o `.env.dockhand` da sua UI.

---

## Apps Docker

Todos os apps abaixo rodam no servidor principal via Docker Compose, gerenciados pelo Dockhand.

---

### Dashboard (Homepage + Dashdot)

**Stack:** `apps/dashboard/`

| Container | Porta | URL |
|---|---|---|
| Homepage | `3001` | `homepage.home.seudominio.com` |
| Dashdot | `3002` | `dashdot.home.seudominio.com` |

**Homepage** é o dashboard principal com widgets para todos os serviços. Configuração em `dockhand_data/stacks/<repo>/homepage/homepage/`.

**Configuração manual:**
- Obter API keys de Sonarr, Radarr, Bazarr, Prowlarr, Overseerr, Jellyfin
- Obter Plex Token em `https://www.plex.tv/claim`
- Preencher no Dockhand: `SONARR_API_KEY`, `RADARR_API_KEY`, etc.

---

### Arrs Stack (Media)

**Stack:** `apps/arrs-stack/`

| Container | Porta | URL |
|---|---|---|
| Homarr | `7575` | `homarr.home.seudominio.com` |
| Overseerr | `5055` | `overseerr.seudominio.com` (público) |
| Prowlarr | `9696` | `prowlarr.home.seudominio.com` |
| Radarr | `7878` | `radarr.home.seudominio.com` |
| Sonarr | `8989` | `sonarr.home.seudominio.com` |
| Bazarr | `6767` | `bazarr.home.seudominio.com` |
| qBittorrent | `8080` | `qbittorrent.home.seudominio.com` |

**Volumes de mídia** (ajustar paths no compose):
- `Downloads` → qBittorrent + Radarr + Sonarr
- `Filmes` → Radarr + Bazarr
- `Series` → Sonarr + Bazarr

**Configuração pós-deploy:**
1. Acessar Prowlarr → adicionar indexers
2. Radarr/Sonarr → Settings → Download Clients → adicionar qBittorrent
3. Radarr/Sonarr → Settings → Indexers → conectar ao Prowlarr
4. Bazarr → Settings → Sonarr e Radarr → conectar
5. Overseerr → setup inicial → conectar ao Plex + Radarr + Sonarr
6. Obter API keys de cada app em Settings → General

**Notificações Telegram (download completo):**

Scripts customizados em `/config/notify-telegram.sh` dentro de cada container. No repo (placeholders): `apps/radarr/notify-telegram.sh` e `apps/sonarr/notify-telegram.sh`. No servidor (valores reais): `/home/<user>/apps/radarr/notify-telegram.sh` e `/home/<user>/apps/sonarr/notify-telegram.sh`.

Configurado via Custom Script notification (Settings → Connect → Custom Script):
- **Path:** `/config/notify-telegram.sh`
- **Triggers:** On Download, On Upgrade

> **Token Telegram:** scripts no repo usam placeholders (`SEU_BOT_TOKEN`/`SEU_CHAT_ID`). No servidor, substituir pelos valores reais (mesmo padrão de `.env`/`.env.example`). Não commitar o token.

Formato das mensagens:
```
# Radarr
🎬 Filme disponível: Título (Ano)
📁 Qualidade: 1080p

# Sonarr
📺 Série disponível: Nome da Série
🗂 Temporada X - Episódio Y
🎞 Título do Episódio
📁 Qualidade: 1080p
```

> **⚠️ Cuidado ao editar via SSH/heredoc:** usar delimitador com aspas (`<< 'EOF'`) para o heredoc **não expandir** as variáveis `$radarr_*`/`$sonarr_*` na hora de gravar o arquivo. Com `<< EOF` (sem aspas), as variáveis são expandidas como vazio no momento da criação → notificação chega sem título/qualidade. Validar sempre com `cat` após gravar.

> Variáveis disponíveis: `$radarr_movie_title`, `$radarr_movie_year`, `$radarr_moviefile_quality` (Radarr) / `$sonarr_series_title`, `$sonarr_episodefile_seasonnumber`, `$sonarr_episodefile_episodenumbers`, `$sonarr_episodefile_episodetitles`, `$sonarr_episodefile_quality` (Sonarr).

**Testar o script manualmente** (passando variáveis simuladas):
```bash
radarr_movie_title='Michael' radarr_movie_year='2026' radarr_moviefile_quality='WEBDL-2160p' \
  bash /home/<user>/apps/radarr/notify-telegram.sh
```

---

### Jellyfin

**Stack:** `apps/jellyfin/`  
**Porta:** `8096`  
**URL:** `jellyfin.home.seudominio.com` (público via tunnel também)

Media server open source.

**Configuração pós-deploy:**
1. Acessar `http://<server-ip>:8096` → setup wizard
2. Adicionar bibliotecas apontando para `/data/movies` e `/data/tvshows`
3. Obter API key em Dashboard → API Keys → gerar nova

---

### Plex

**Stack:** `apps/plex/`  
**Modo:** `network_mode: host`  
**URL:** `plex.home.seudominio.com`

Roda em modo host (necessário para discovery na rede local).

**Configuração pós-deploy:**
1. Acessar `http://<server-ip>:32400/web`
2. Login com conta Plex
3. Adicionar bibliotecas

---

### Monitoring Stack (Netdata + Prometheus + Grafana)

**Stack:** `apps/monitoring-stack/`

| Container | Porta | URL |
|---|---|---|
| Netdata | `19999` | `netdata.home.seudominio.com` |
| Prometheus | `9090` | `prometheus.home.seudominio.com` |
| Grafana | `3003` | `grafana.home.seudominio.com` |
| Node Exporter | host network | interno |

Netdata (container no homelab) é o **parent** que agrega métricas. Prometheus faz scrape do parent. Grafana visualiza os dados do Prometheus.

**Configuração manual:**
- `prometheus.yml` → copiar para `/home/<user>/apps/monitoring-stack/prometheus.yml` no servidor (Dockhand não sincroniza arquivos extras)
- Datasources do Grafana em `/home/<user>/apps/grafana/provisioning/datasources/prometheus.yml`
- Dashboard: `apps/monitoring-stack/grafana-dashboard.json` → importar via Grafana UI (não sincroniza auto)
- Grafana login padrão: `admin/admin` (trocar no primeiro acesso)
- Netdata também conecta ao Netdata Cloud (painel em `app.netdata.cloud`)

#### Monitoramento dos nodes Proxmox (Leon + Claire)

Leon e Claire rodam **Netdata bare metal** (não LXC — sensores de hardware precisam de acesso direto). Cada um faz streaming das métricas para o parent (homelab).

**Instalação em cada node:**
```bash
curl -Ss -L https://my-netdata.io/kickstart.sh > /tmp/netdata-install.sh
bash /tmp/netdata-install.sh --non-interactive --stable-channel
```

**Streaming child → parent** — em cada node, `/etc/netdata/stream.conf`:
```ini
[stream]
    enabled = yes
    destination = <homelab-ip>:19999
    api key = <STREAM_API_KEY>
```

**Parent aceita streaming** — dentro do container netdata, `/etc/netdata/stream.conf`:
```ini
[<STREAM_API_KEY>]
    enabled = yes
    allow from = 192.168.3.*
```
> Gerar `STREAM_API_KEY` via `uuidgen`. Uma key por node (mais controle).

**Prometheus scrape** — usa format `prometheus_all_hosts` para expor todos os hosts com label `instance`:
```yaml
- job_name: 'netdata'
  metrics_path: '/api/v1/allmetrics'
  params:
    format: ['prometheus_all_hosts']
  honor_labels: true
  static_configs:
    - targets: ['netdata:19999']
```

**Queries Grafana:**
- Métricas do homelab: filtrar `instance!~"leon|claire"` (senão soma os 3 nodes → valores errados)
- Métricas dos nodes: filtrar `instance=~"leon|claire"`
- Temperatura: `netdata_system_hw_sensor_temperature_input_degrees_Celsius_average{chart=~".*coretemp.*Package.*"}`
- Temp disco: `netdata_smartctl_device_temperature_Celsius_average` (SSD/HD) ou `chart=~".*nvme.*Composite.*"` (NVMe)

> Dashboard tem row "Proxmox Nodes" com CPU/RAM por node + bargauge de temperatura (CPU + disco) lado a lado.

---

### Nextcloud

**Stack:** `apps/nextcloud/`  
**Porta:** `8383`  
**URL:** `nextcloud.home.seudominio.com` / `nextcloud.seudominio.com`

Servidor de arquivos e produtividade self-hosted.

| Container | Imagem | Função |
|---|---|---|
| `nextcloud` | `nextcloud:latest` | App principal |
| `nextcloud-db` | `mariadb:lts` | Banco de dados |

**Volumes no servidor:**
- `/home/<user>/apps/nextcloud/config` → config PHP
- `/home/<user>/apps/nextcloud/data` → dados dos usuários
- `/home/<user>/apps/nextcloud/db` → dados do MariaDB

**Configuração pós-deploy:**
1. Acessar a URL → setup wizard
2. Usar credenciais definidas nas vars `NEXTCLOUD_ADMIN_USER` e `NEXTCLOUD_ADMIN_PASSWORD`
3. Banco é configurado automaticamente via variáveis de ambiente

**Manutenção via CLI (dentro do container):**
```bash
# Rodar comandos occ
docker exec -u 1000 nextcloud php occ <comando>

# Exemplo: forçar upgrade após atualização de imagem
docker exec -u 1000 nextcloud php occ upgrade
```

> Se aparecer "Cannot write into config directory", corrigir permissões:
> `docker exec nextcloud chown -R www-data:www-data /var/www/html/config`

---

### Syncthing

**Stack:** `apps/syncthing/`  
**Porta:** `8384`  
**URL:** `syncthing.home.seudominio.com`

Sincronização de arquivos P2P. Volume de sync: `/mnt/homelab-hd-interno/SYNCTHING`.

---

### Filebrowser

**Stack:** `apps/filebrowser/`  
**Porta:** `8181`  
**URL:** `filebrowser.home.seudominio.com`

Navegador de arquivos web. Login padrão: `admin/admin` (trocar no primeiro acesso).

---

### Uptime Kuma

**Stack:** `apps/uptime-kuma/`  
**URL:** `uptime-kuma.home.seudominio.com`

Monitor de disponibilidade de serviços. Sem porta de host exposta — acesso exclusivamente via Traefik.

---

### Heimdall

**Stack:** `apps/heimdall/`  
**Portas:** `81:80`, `446:443`  
**URL:** `heimdall.home.seudominio.com`

Dashboard de links para serviços. Alternativa ao Homepage para acesso rápido.

---

### AdGuard Home Sync

**Stack:** `apps/adguardhome-sync/`

Sincroniza configurações do AdGuard primário para o secundário a cada hora.

**Configuração:** editar `adguardhome-sync.yaml` com IPs e credenciais (baseado no `.yaml.example`).

---

### Time Machine

**Stack:** `apps/time-machine/`  
**Modo:** `network_mode: host`

Servidor Samba para backup Time Machine de Macs na rede.

**Configuração:** alterar `PASSWORD` e `VOLUME_SIZE_LIMIT` (0 = sem limite) no compose.

---

### Tailscale

**Stack:** `apps/tailscale/`  
**Modo:** `network_mode: host`

Anuncia a sub-rede local para a mesh Tailscale.

**Configuração:**
1. Gerar auth key em `https://login.tailscale.com/admin/settings/keys`
2. Preencher `TS_AUTHKEY` no Dockhand
3. Após deploy, aprovar sub-rede no painel Tailscale admin
4. Ajustar `--advertise-routes` no compose com o CIDR da sua rede

---

### Watchtower

**Stack:** `apps/watchtower/`

Atualiza automaticamente imagens Docker toda quarta-feira às 3h. Remove imagens antigas automaticamente.

---

### Netdata

**Stack:** `apps/netdata/`  
**Modo:** `network_mode: host`

Monitoramento em tempo real. Interface em `http://<server-ip>:19999`.

---

## Containers LXC

Gerenciados diretamente no Proxmox. Não são Docker — são containers LXC Proxmox.

### AdGuard Secondary

- **Startup:** `order=1, onboot=1`
- **URL:** `adguard-secondary.home.seudominio.com`
- **Instalado via:** [community-scripts.org](https://community-scripts.org/scripts/adguard)

DNS secundário. Sincronizado automaticamente pelo AdGuard Home Sync.

### Tailscale (node secundário)

Mantém acesso Tailscale ao node Claire independente do servidor principal.

### UPSnap (Wake on LAN)

- **Porta:** `8090`
- **Startup:** `order=1, onboot=1`
- **URL:** `upsnap.home.seudominio.com`
- **Serviço:** `upsnap.service` (systemd)
- **Login:** conta PocketBase (email do administrador)

Interface web para ligar dispositivos via Wake on LAN.

#### Devices configurados

| Device | IP | MAC |
|---|---|---|
| Leon (Proxmox) | `PROXMOX_LEON_IP` | `<MAC_LEON>` |

#### Integração com Alexa (Remote Relay)

WoL via Alexa funciona via **Remote Relay** (LXC no Claire — serviço sempre on). Remote Relay envia magic packet pra todos os MACs cadastrados no device com um único comando.

Device "Homelab" no Remote Relay tem dois MACs:
- `<MAC_HOMELAB>` — servidor Docker principal
- `<MAC_LEON>` — Proxmox Leon

Comando: *"Alexa, liga o Homelab"* → acorda ambos simultaneamente.

> SimpleWOL não funciona para Linux — requer agente local não compatível. Remote Relay é a solução correta.

#### Requisito: habilitar WoL no dispositivo alvo

No node a ser ligado remotamente, verificar e habilitar WoL:

```bash
# Verificar suporte e status
ethtool <interface> | grep -i wake

# Habilitar (ex: enp1s0)
ethtool -s <interface> wol g
```

Para persistir após reboot, criar serviço systemd:

```ini
# /etc/systemd/system/wol-<hostname>.service
[Unit]
Description=Enable Wake-on-LAN
After=network.target

[Service]
Type=oneshot
ExecStart=/sbin/ethtool -s <interface> wol g
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable wol-<hostname> && systemctl start wol-<hostname>
```

> No Leon: serviço `/etc/systemd/system/wol-leon.service`, interface `enp1s0`. WoL verificado e funcionando.

#### Criar LXC UPSnap do zero (sem community scripts)

```bash
# 1. Verificar templates disponíveis no node
pveam list local

# 2. Criar LXC
pvesh create /nodes/<node>/lxc \
  --vmid <ID> \
  --hostname upsnap \
  --memory 512 \
  --swap 512 \
  --cores 1 \
  --rootfs local:2 \
  --net0 name=eth0,bridge=vmbr0,ip=<IP>/24,gw=<GATEWAY> \
  --ostemplate local:vztmpl/<template>.tar.zst \
  --onboot 1 \
  --startup order=1 \
  --timezone America/Sao_Paulo \
  --unprivileged 1 \
  --nameserver <DNS_IP>

# 3. Ativar nesting e iniciar
pvesh set /nodes/<node>/lxc/<ID>/config --features nesting=1
pct start <ID>

# 4. Instalar UPSnap
pct exec <ID> -- bash -c "
  apt-get update -qq && apt-get install -y curl unzip &&
  curl -fsSL https://github.com/seriousm4x/UpSnap/releases/download/5.3.5/UpSnap_5.3.5_linux_amd64.zip -o /tmp/upsnap.zip &&
  mkdir -p /opt/upsnap && unzip -q /tmp/upsnap.zip -d /opt/upsnap &&
  chmod +x /opt/upsnap/upsnap
"

# 5. Criar serviço systemd
pct exec <ID> -- bash -c "cat > /etc/systemd/system/upsnap.service << 'EOF'
[Unit]
Description=UpSnap Wake on LAN
After=network.target

[Service]
Type=simple
Environment=HOME=/root
WorkingDirectory=/opt/upsnap
ExecStart=/opt/upsnap/upsnap serve --http=0.0.0.0:8090
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable upsnap && systemctl start upsnap"
```

---

## MCP SSH Server

**Stack:** `apps/mcp-ssh-server/`  
**Porta:** `8765`  
**URL pública:** `mcp.seudominio.com/mcp`  
**URL local:** `mcp.home.seudominio.com/mcp`

Servidor MCP (Model Context Protocol) que expõe ferramentas de controle do homelab para assistentes de IA (Claude, etc.).

### Ferramentas disponíveis

| Categoria | Ferramentas |
|---|---|
| Docker | `docker_list_containers`, `docker_container_action`, `docker_container_logs`, `docker_logs_grep`, `docker_container_stats`, `docker_exec_command`, `docker_container_env` |
| SSH | `ssh_exec`, `ssh_read_file`, `ssh_list_dir` |
| Traefik | `traefik_list_routes` |
| Saúde | `check_service_health` |
| Proxmox | `proxmox_node_status`, `proxmox_node_action`, `proxmox_list_vms`, `proxmox_vm_action`, `proxmox_vm_config`, `proxmox_vm_detach_disk`, `proxmox_vm_resize_disk`, `proxmox_vm_snapshot`, `proxmox_vm_list_snapshots`, `proxmox_vm_rollback`, `proxmox_backup_status`, `proxmox_list_all_backups`, `proxmox_storage_status` |

### Hosts SSH disponíveis

Configurados via variáveis de ambiente:

| Variável | Host alvo | Usuário |
|---|---|---|
| `SSH_HOST_HOMELAB` + `SSH_USER` | Servidor principal | usuário local |
| `PROXMOX_LEON_IP` | Node Leon | `root` |
| `PROXMOX_CLAIRE_IP` | Node Claire | `root` |

SSH key montada em `/root/.ssh` dentro do container (volume `~/.ssh:/root/.ssh:ro`).

### Autenticação OAuth (Claude.ai)

O servidor implementa OAuth 2.0 Authorization Code + PKCE para conectores remotos do Claude.ai. O token bearer é configurado via `MCP_AUTH_TOKEN` no `.env`.

### Build e deploy

```bash
# Build da imagem
docker build -t mcp-ssh-server:latest apps/mcp-ssh-server/

# Deploy via Dockhand (recomendado)
# Ou manualmente:
cd apps/mcp-ssh-server
docker compose --env-file .env up -d --force-recreate
```

> Após restart do container, é necessário reconectar o conector MCP no Claude.ai (a sessão OAuth expira).

### Conectar no Claude.ai

1. Acessar `claude.ai` → Settings → Connectors
2. Adicionar conector remoto com URL: `https://mcp.seudominio.com`
3. Autenticar via OAuth (fluxo automático)
4. Ativar o conector na conversa (toggle no painel de ferramentas)

---

## Scripts de Manutenção

Localizados em `apps/scripts/`.

### backup-apps.sh

Faz backup compactado de `/home/<user>/apps/` com política de retenção e sincronização com Google Drive via rclone.

**Política de retenção:**
- 3 backups mais recentes
- 1 backup com 7+ dias

**Dependências:**
- rclone configurado e autenticado com Google Drive

```bash
# Rodar manualmente
bash apps/scripts/backup-apps.sh

# Agendar via cron (ex: diariamente às 2h)
0 2 * * * /path/to/homelab/apps/scripts/backup-apps.sh
```

### docker-cleanup.sh

Remove imagens Docker antigas (não-latest, não em uso). Preserva imagens com tag `latest` e imagens usadas por containers ativos ou parados.

```bash
bash apps/scripts/docker-cleanup.sh
```

---

## Proxmox Leon — Configurações Específicas

### USB Disk Passthrough Resiliente (VM 110)

VM 110 (`homelab`) tem o HD externo Seagate BUP Slim (`scsi1`) em passthrough. Como é USB, pode desconectar — sem tratamento, a VM falha ao iniciar.

**Solução implementada:** script + systemd service + udev rules que gerenciam `scsi1` automaticamente.

| Arquivo | Localização no Leon |
|---|---|
| Script | `/usr/local/bin/check-usb-disk-vm110.sh` |
| Systemd service | `/etc/systemd/system/check-usb-disk-vm110.service` |
| udev rules | `/etc/udev/rules.d/99-seagate-vm110.rules` |

**Comportamento:**

| Cenário | O que acontece |
|---|---|
| Boot com disco ausente | systemd service remove `scsi1` da config → VM inicia normalmente |
| Boot com disco presente | systemd service garante `scsi1` na config |
| Disco desconecta em runtime | udev REMOVE → `scsi1` removido da config |
| Disco reconecta em runtime | udev ADD → `scsi1` reanexado na config |
| Disco ausente com VM já rodando | VM continua mas perde I/O do disco — requer restart manual |

> `qm set --delete scsi1` apenas remove a referência na config — **não apaga dados do disco**.

**Verificar logs:**
```bash
journalctl -t check-usb-disk
```

**Rodar manualmente:**
```bash
bash /usr/local/bin/check-usb-disk-vm110.sh
```

---

## Acesso Externo

### Via Cloudflare Tunnel (público)

Serviços selecionados expostos publicamente via tunnel. Configurar quais serviços usar o entrypoint `tunnel` nos labels do compose.

### Via Tailscale (privado)

Qualquer dispositivo na mesh Tailscale acessa todos os serviços `*.home.seudominio.com` como se estivesse na rede local.

**Configuração no cliente:**
1. Instalar Tailscale no dispositivo
2. Login na mesma conta
3. Habilitar uso das rotas anunciadas no painel Tailscale admin
4. Configurar DNS do Tailscale para usar o AdGuard como nameserver

---

## Variáveis de Ambiente

Cada stack tem um `.env.example` com todas as variáveis necessárias. O `.env` real é gitignored — configurar via Dockhand UI ou localmente para testes.

| Stack | Vars principais |
|---|---|
| `traefik` | `CF_DNS_API_TOKEN`, `CLOUDFLARE_TUNNEL_TOKEN`, domínios, IPs dos serviços |
| `dashboard` | API keys de todos os serviços, `PROXMOX_TOKEN_SECRET` |
| `arrs-stack` | Domínios dos serviços arr |
| `mcp-ssh-server` | `MCP_AUTH_TOKEN`, `MCP_PUBLIC_DOMAIN`, `PROXMOX_TOKEN_SECRET`, `SSH_USER`, `SSH_HOST_HOMELAB` |
| `tailscale` | `TS_AUTHKEY` |
