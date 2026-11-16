# Homelab

Complete documentation of the homelab infrastructure, Docker stacks and procedures.

---

## Table of Contents

- [Architecture](#architecture)
- [Hardware and Infrastructure](#hardware-and-infrastructure)
- [Network](#network)
- [Prerequisites](#prerequisites)
- [Base Installation](#base-installation)
- [Traefik](#traefik)
- [Dockhand](#dockhand)
- [Docker Apps](#docker-apps)
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
  - [AdGuard Home Sync](#adguard-home-sync-1)
  - [Time Machine](#time-machine)
  - [Tailscale](#tailscale)
  - [Watchtower](#watchtower)
- [LXC Containers](#lxc-containers)
- [MCP SSH Server](#mcp-ssh-server)
- [Maintenance Scripts](#maintenance-scripts)
- [Resource Limits](#resource-limits)
- [Optional Proxmox Node Optimizations](#optional-proxmox-node-optimizations)
- [External Access](#external-access)
- [Environment Variables](#environment-variables)

---

## Architecture

```
Internet
    │
Cloudflare DNS + Tunnel
    │
    ├── Traefik (reverse proxy, port 443)
    │       └── Docker containers via labels
    │       └── LXC / VMs via dynamic.yml
    │
    ├── Tailscale (mesh VPN, local subnet)
    │
Main Server
    │
    ├── Primary Proxmox node
    │       └── VMs and guests (e.g. the Docker server VM)
    │
    └── Secondary Proxmox node (ideally always on)
            └── LXC AdGuard Secondary
            └── LXC Tailscale
            └── LXC UPSnap (Wake on LAN)
```

---

## Hardware and Infrastructure

| Device | Variable | Role |
|---|---|---|
| Main server | `SERVER_IP` | Runs all Docker containers (can be a VM on a Proxmox node) |
| Primary Proxmox node | `PROXMOX_NODE1_IP` | Main hypervisor |
| Secondary Proxmox node | `PROXMOX_NODE2_IP` | Secondary hypervisor (ideally always on, for WoL) |
| AdGuard Primary | `ADGUARD_IP` | Primary network DNS |
| AdGuard Secondary | `ADGUARD_SECONDARY_IP` | Secondary DNS |
| UPSnap | `UPSNAP_IP` | Wake on LAN |

All IPs are defined in each stack's `.env` file (see `.env.example`).

### Proxmox API Token

Used by Homepage and the MCP Server to query node/VM status:

```
PVEAPIToken=root@pam!<TOKEN_NAME>=<TOKEN_SECRET>
```

Generate at: Proxmox → Datacenter → API Tokens.

---

## Network

### Domain convention

Two types of access:

| Suffix | Access | How it works |
|---|---|---|
| `*.seudominio.com` | Public via Cloudflare Tunnel | Cloudflare → Traefik port 8080 |
| `*.home.seudominio.com` | Local via Tailscale/internal network | DNS resolves directly → Traefik port 443 |

### Cloudflare Tunnel

The `cloudflared` container creates a persistent tunnel to Cloudflare. Traefik has a `tunnel` entrypoint on port `8080` to receive this traffic.

Configured in `apps/traefik/cloudflared-config.yml`.

### AdGuard Home Sync

Syncs settings from the primary AdGuard to the secondary every hour. Configured in `apps/adguardhome-sync/adguardhome-sync.yaml` (based on `.yaml.example`).

---

## Prerequisites

On the main server:

- Docker Engine + Docker Compose plugin
- User with Docker access (`usermod -aG docker <user>`)
- SSH key configured (`~/.ssh/`) and distributed to the Proxmox nodes
- External Docker network created:

```bash
docker network create traefik
```

- `acme.json` file with correct permissions:

```bash
touch /home/<user>/apps/traefik/acme.json
chmod 600 /home/<user>/apps/traefik/acme.json
```

---

## Base Installation

### Directory structure on the server

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

### Deploy flow with Dockhand

1. Edit files in the local repo
2. Run `git push`
3. Dockhand detects the branch change and updates the stack automatically
4. For stacks with volume files outside the compose file (e.g. Traefik's `dynamic.yml`), copy them manually to `/home/<user>/apps/<stack>/`

> **Important:** Dockhand overwrites `.env` with `.env.dockhand`, managed through its UI. New environment variables must be added both in `docker-compose.yaml` (`environment` section) and in the Dockhand UI.

---

## Traefik

**Image:** `traefik:v3`  
**Main file:** `apps/traefik/traefik.yml`  
**Dynamic routing:** `apps/traefik/dynamic.yml`

### Entrypoints

| Name | Port | Use |
|---|---|---|
| `web` | `80` | Redirects to `websecure` |
| `websecure` | `443` | Main HTTPS (local + Tailscale) |
| `tunnel` | `8080` | Cloudflare Tunnel |

### Certificates

Generated automatically via DNS Challenge with Cloudflare (`CF_DNS_API_TOKEN`). Stored in `acme.json`.

### Manual post-deploy configuration

1. Copy `dynamic.yml` to `/home/<user>/apps/traefik/dynamic.yml` if it changed
2. Traefik reloads automatically (`watch: true`) — no restart needed for `dynamic.yml` changes
3. For `.env` or `docker-compose.yaml` changes: force-recreate required

```bash
cd /home/<user>/apps/dockhand/dockhand_data/stacks/<repo>/traefik
docker compose --env-file .env.dockhand up -d --force-recreate
```

### Services routed via dynamic.yml (no Docker labels)

| Service | Domain (var) | Backend |
|---|---|---|
| Primary Proxmox node | `PROXMOX_NODE1_HOME_DOMAIN` | `https://<PROXMOX_NODE1_IP>:8006` |
| Secondary Proxmox node | `PROXMOX_NODE2_HOME_DOMAIN` | `https://<PROXMOX_NODE2_IP>:8006` |
| AdGuard Primary | `ADGUARD_HOME_DOMAIN` | `http://<ADGUARD_IP>:<ADGUARD_PORT>` |
| AdGuard Secondary | `ADGUARD_SECONDARY_HOME_DOMAIN` | `http://<ADGUARD_SECONDARY_IP>:<ADGUARD_PORT>` |
| Plex | `PLEX_HOME_DOMAIN` | `http://<SERVER_IP>:32400` |
| UPSnap | `UPSNAP_HOME_DOMAIN` | `http://<UPSNAP_IP>:8090` |

> Proxmox uses `serversTransport: insecure` (skip TLS verify) because its certificate is self-signed.

### Adding a new LXC/VM service to Traefik

1. Add a router and service in `dynamic.yml`
2. Add `NEW_DOMAIN` and `NEW_IP` to Traefik's `docker-compose.yaml` (`environment` section)
3. Add the vars to `.env.example` and the Dockhand UI
4. Copy the updated `dynamic.yml` to the server
5. Force-recreate Traefik to load the new vars

---

## Dockhand

**Image:** `fnsys/dockhand:latest`  
**Port:** `3000`  
**URL:** `dockhand.home.seudominio.com`

Manages Docker stacks from a Git repository. Watches branches and redeploys automatically when it detects changes.

### Initial setup

1. Open `http://<server-ip>:3000`
2. Create an admin account
3. Add the Git repository (HTTPS or SSH)
4. For each stack: add the environment variables in the "Environment" tab
5. Dockhand creates the `.env.dockhand` file in the stack directory

### Adding a new variable to an existing stack

1. In the stack's `docker-compose.yaml`, add the var to the `environment` section
2. Commit and push
3. In the Dockhand UI, go to the stack → "Environment" → add the var with its real value
4. Dockhand redeploys automatically (or click "Deploy")

> Dockhand does **not** use the repo's `.env` — only the `.env.dockhand` from its UI.

---

## Docker Apps

All apps below run on the main server via Docker Compose, managed by Dockhand.

---

### Dashboard (Homepage + Dashdot)

**Stack:** `apps/dashboard/`

| Container | Port | URL |
|---|---|---|
| Homepage | `3001` | `homepage.home.seudominio.com` |
| Dashdot | `3002` | `dashdot.home.seudominio.com` |

**Homepage** is the main dashboard with widgets for every service. Configuration lives in `dockhand_data/stacks/<repo>/homepage/homepage/`.

**Manual configuration:**
- Get API keys from Sonarr, Radarr, Bazarr, Prowlarr, Overseerr, Jellyfin
- Get the Plex Token at `https://www.plex.tv/claim`
- Fill them in Dockhand: `SONARR_API_KEY`, `RADARR_API_KEY`, etc.

---

### Arrs Stack (Media)

**Stack:** `apps/arrs-stack/`

| Container | Port | URL |
|---|---|---|
| Homarr | `7575` | `homarr.home.seudominio.com` |
| Overseerr | `5055` | `overseerr.seudominio.com` (public) |
| Prowlarr | `9696` | `prowlarr.home.seudominio.com` |
| Radarr | `7878` | `radarr.home.seudominio.com` |
| Sonarr | `8989` | `sonarr.home.seudominio.com` |
| Bazarr | `6767` | `bazarr.home.seudominio.com` |
| qBittorrent | `8080` | `qbittorrent.home.seudominio.com` |

**Media volumes — single mount for hardlinks:**

Radarr, Sonarr, qBittorrent and Bazarr mount **a single volume** `/data` (not separate subfolders):
```yaml
- /mnt/homelab-hd-externo/MEDIA_CENTER:/data
```

Internal layout (`/data` in the container = `MEDIA_CENTER` on the host):
| Internal path | Contents |
|---|---|
| `/data/Downloads` | qBittorrent save path |
| `/data/Filmes` | Radarr root folder (movies) |
| `/data/Series` | Sonarr root folder |

> **Why a single mount:** hardlinks only work within the same mount. With separate `/movies` + `/downloads` (distinct bind mounts), imports become **copies** (double the space, burn CPU/IO). With a single `/data`, Radarr/Sonarr create a **hardlink** from the download to the library → instant import, zero extra space, seeding continues from the same file. See [TRaSH Guides — Hardlinks](https://trash-guides.info/Hardlinks/Hardlinks-and-Instant-Moves/).

> **Verify hardlinks:**
> ```bash
> docker exec radarr sh -c 'touch /data/Downloads/.hl && ln /data/Downloads/.hl /data/Filmes/.hl && echo OK; rm -f /data/Downloads/.hl /data/Filmes/.hl'
> ```
> If it returns `Cross-device link` → mounts are still separate (hardlinks broken).

> **Plex and Jellyfin don't need `/data`** — they only read the final library (`Filmes`/`Series`). They keep their own mounts, with no impact on watch history.

**Internal configuration (root folders / save path):**
- Radarr → Settings → Media Management → Root Folder: `/data/Filmes`
- Sonarr → Settings → Media Management → Root Folder: `/data/Series`
- qBittorrent → Options → Downloads → Save Path: `/data/Downloads`, Incomplete: `/data/Downloads/incomplete`
- Bazarr uses Radarr/Sonarr paths (empty path_mappings) — works automatically with `/data`

> **Migrating from separate mounts → `/data`** (remap without moving files): use the Radarr `movie/editor` and Sonarr `series/editor` APIs with `moveFiles:false` (only updates paths in the DB, files stay in place). Also update Radarr **collections** (`rootFolderPath`) and active qBittorrent torrents via `setLocation` + recheck.

**qBittorrent runtime config** (in `qBittorrent.conf`, in the `/config` volume — **not** versioned; edit with the container stopped, since qBit rewrites it on shutdown):
```ini
Session\DefaultSavePath=/data/Downloads
Session\TempPath=/data/Downloads/incomplete
WebUI\LocalHostAuth=false                  # allows API via localhost inside the container
WebUI\AuthSubnetWhitelistEnabled=true      # clients on the Docker subnet skip auth
WebUI\AuthSubnetWhitelist=<docker-subnet>  # e.g. 172.16.0.0/12
```
> The subnet whitelist fixes the "Invalid cookie" error from clients that integrate with qBit (e.g. the homarr dashboard with newer qBit versions).

**Post-deploy configuration:**
1. Open Prowlarr → add indexers
2. Radarr/Sonarr → Settings → Download Clients → add qBittorrent
3. Radarr/Sonarr → Settings → Indexers → connect to Prowlarr
4. Bazarr → Settings → Sonarr and Radarr → connect
5. Overseerr → initial setup → connect to Plex + Radarr + Sonarr
6. Get each app's API key under Settings → General

**Telegram notifications (download completed):**

Custom scripts at `/config/notify-telegram.sh` inside each container. In the repo (placeholders): `apps/radarr/notify-telegram.sh` and `apps/sonarr/notify-telegram.sh`. On the server (real values): `/home/<user>/apps/radarr/notify-telegram.sh` and `/home/<user>/apps/sonarr/notify-telegram.sh`.

Configured as a Custom Script notification (Settings → Connect → Custom Script):
- **Path:** `/config/notify-telegram.sh`
- **Triggers:** On Download, On Upgrade

> **Telegram token:** the repo scripts use placeholders (`SEU_BOT_TOKEN`/`SEU_CHAT_ID`). On the server, replace them with the real values (same pattern as `.env`/`.env.example`). Never commit the token.

Message format (sent in Portuguese):
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

> **⚠️ Careful when editing via SSH/heredoc:** use a quoted delimiter (`<< 'EOF'`) so the heredoc does **not expand** the `$radarr_*`/`$sonarr_*` variables when writing the file. With `<< EOF` (unquoted), the variables expand to empty at creation time → notifications arrive without title/quality. Always verify with `cat` after writing.

> Available variables: `$radarr_movie_title`, `$radarr_movie_year`, `$radarr_moviefile_quality` (Radarr) / `$sonarr_series_title`, `$sonarr_episodefile_seasonnumber`, `$sonarr_episodefile_episodenumbers`, `$sonarr_episodefile_episodetitles`, `$sonarr_episodefile_quality` (Sonarr).

**Test the script manually** (passing simulated variables):
```bash
radarr_movie_title='Michael' radarr_movie_year='2026' radarr_moviefile_quality='WEBDL-2160p' \
  bash /home/<user>/apps/radarr/notify-telegram.sh
```

---

### Jellyfin

**Stack:** `apps/jellyfin/`  
**Port:** `8096`  
**URL:** `jellyfin.home.seudominio.com` (also public via tunnel)

Open source media server.

**Post-deploy configuration:**
1. Open `http://<server-ip>:8096` → setup wizard
2. Add libraries pointing to `/data/movies` and `/data/tvshows`
3. Get an API key under Dashboard → API Keys → generate new

---

### Plex

**Stack:** `apps/plex/`  
**Mode:** `network_mode: host`  
**URL:** `plex.home.seudominio.com`

Runs in host mode (required for local network discovery).

**Post-deploy configuration:**
1. Open `http://<server-ip>:32400/web`
2. Log in with a Plex account
3. Add libraries

---

### Monitoring Stack (Netdata + Prometheus + Grafana)

**Stack:** `apps/monitoring-stack/`

| Container | Port | URL |
|---|---|---|
| Netdata | `19999` | `netdata.home.seudominio.com` |
| Prometheus | `9090` | `prometheus.home.seudominio.com` |
| Grafana | `3003` | `grafana.home.seudominio.com` |
| Node Exporter | host network | internal |

Netdata (container on the homelab) is the **parent** that aggregates metrics. Prometheus scrapes the parent. Grafana visualizes the Prometheus data.

**Manual configuration:**
- `prometheus.yml` → copy to `/home/<user>/apps/monitoring-stack/prometheus.yml` on the server (Dockhand doesn't sync extra files)
- Grafana datasources in `/home/<user>/apps/grafana/provisioning/datasources/prometheus.yml`
- Dashboard: `apps/monitoring-stack/grafana-dashboard.json` → import via the Grafana UI (not synced automatically)
- Default Grafana login: `admin/admin` (change on first login)
- Netdata also connects to Netdata Cloud (dashboard at `app.netdata.cloud`)

#### Netdata tuning (reduces CPU)

By default Netdata collects cgroup metrics (every container) every 1s. On modest hardware this significantly raises `dockerd`+`containerd` CPU usage. Lowering the collection frequency fixes it — reference config in `apps/monitoring-stack/netdata-tuning.conf`.

```bash
# netdata.conf lives in the monitoring-stack_netdataconfig Docker volume (Dockhand does NOT sync it)
docker exec netdata bash -c 'cat >> /etc/netdata/netdata.conf << EOF

[global]
    update every = 5

[plugin:cgroups]
    update every = 30
    enable new cgroups detected at runtime = yes

[plugin:proc:/proc/diskstats]
    update every = 10
EOF'
docker restart netdata
```

> Verify: `docker exec netdata grep -A1 'plugin:cgroups' /etc/netdata/netdata.conf`

#### Monitoring Proxmox nodes (child → parent streaming)

To include the Proxmox nodes (CPU, RAM, temperature) in the same Grafana, run **bare metal Netdata** on each node (not LXC — hardware sensors need direct access) streaming to the parent (the homelab's Netdata container).

**Install on each node:**
```bash
curl -Ss -L https://my-netdata.io/kickstart.sh -o /tmp/netdata-install.sh
bash /tmp/netdata-install.sh --non-interactive --stable-channel
```

**Child → parent** — on each node, `/etc/netdata/stream.conf`:
```ini
[stream]
    enabled = yes
    destination = <homelab-ip>:19999
    api key = <STREAM_API_KEY>   # generate with uuidgen (one key per node)
```

**Parent accepts streaming** — in the netdata container, `/etc/netdata/stream.conf`:
```ini
[<STREAM_API_KEY>]
    enabled = yes
    allow from = <local-subnet>
```

**Prometheus scrape** — the `prometheus_all_hosts` format exposes every host with an `instance` label:
```yaml
- job_name: 'netdata'
  metrics_path: '/api/v1/allmetrics'
  params:
    format: ['prometheus_all_hosts']
  honor_labels: true
  static_configs:
    - targets: ['netdata:19999']
```

**Grafana queries** (with multiple hosts in the same job):
- Filter the main host: `instance!~"<node1>|<node2>"` (otherwise all hosts are summed → wrong values)
- Filter the nodes: `instance=~"<node1>|<node2>"`
- CPU temperature: `netdata_system_hw_sensor_temperature_input_degrees_Celsius_average{chart=~".*coretemp.*Package.*"}`
- Disk temperature: `netdata_smartctl_device_temperature_Celsius_average` (SSD/HDD) or `chart=~".*nvme.*Composite.*"` (NVMe)

---

### Nextcloud

**Stack:** `apps/nextcloud/`  
**Port:** `8383`  
**URL:** `nextcloud.home.seudominio.com` / `nextcloud.seudominio.com`

Self-hosted file and productivity server.

| Container | Image | Role |
|---|---|---|
| `nextcloud` | `nextcloud:latest` | Main app |
| `nextcloud-db` | `mariadb:lts` | Database |

**Volumes on the server:**
- `/home/<user>/apps/nextcloud/config` → PHP config
- `/home/<user>/apps/nextcloud/data` → user data
- `/home/<user>/apps/nextcloud/db` → MariaDB data

**Post-deploy configuration:**
1. Open the URL → setup wizard
2. Use the credentials set in the `NEXTCLOUD_ADMIN_USER` and `NEXTCLOUD_ADMIN_PASSWORD` vars
3. The database is configured automatically via environment variables

**Maintenance via CLI (inside the container):**
```bash
# Run occ commands
docker exec -u 1000 nextcloud php occ <command>

# Example: force an upgrade after an image update
docker exec -u 1000 nextcloud php occ upgrade
```

> If you see "Cannot write into config directory", fix the permissions:
> `docker exec nextcloud chown -R www-data:www-data /var/www/html/config`

---

### Syncthing

**Stack:** `apps/syncthing/`  
**Port:** `8384`  
**URL:** `syncthing.home.seudominio.com`

P2P file sync. Sync volume: `/mnt/homelab-hd-interno/SYNCTHING`.

---

### Filebrowser

**Stack:** `apps/filebrowser/`  
**Port:** `8181`  
**URL:** `filebrowser.home.seudominio.com`

Web file browser. Default login: `admin/admin` (change on first login).

---

### Uptime Kuma

**Stack:** `apps/uptime-kuma/`  
**URL:** `uptime-kuma.home.seudominio.com`

Service availability monitor. No host port exposed — access only through Traefik.

---

### Heimdall

**Stack:** `apps/heimdall/`  
**Ports:** `81:80`, `446:443`  
**URL:** `heimdall.home.seudominio.com`

Link dashboard for services. Alternative to Homepage for quick access.

---

### AdGuard Home Sync

**Stack:** `apps/adguardhome-sync/`

Syncs settings from the primary AdGuard to the secondary every hour.

**Configuration:** edit `adguardhome-sync.yaml` with IPs and credentials (based on `.yaml.example`).

---

### Time Machine

**Stack:** `apps/time-machine/`  
**Mode:** `network_mode: host`

Samba server for Time Machine backups of Macs on the network.

**Configuration:** change `PASSWORD` and `VOLUME_SIZE_LIMIT` (0 = unlimited) in the compose file.

---

### Tailscale

**Stack:** `apps/tailscale/`  
**Mode:** `network_mode: host`

Advertises the local subnet to the Tailscale mesh.

**Configuration:**
1. Generate an auth key at `https://login.tailscale.com/admin/settings/keys`
2. Fill `TS_AUTHKEY` in Dockhand
3. After deploying, approve the subnet in the Tailscale admin panel
4. Adjust `--advertise-routes` in the compose file to your network's CIDR

---

### Watchtower

**Stack:** `apps/watchtower/`

Updates Docker images automatically (configurable schedule). With `WATCHTOWER_CLEANUP=true`, it removes the old image after updating — but it doesn't clean up orphaned images in general (see `docker-cleanup.sh`).

---

## LXC Containers

Managed directly in Proxmox. These are not Docker — they are Proxmox LXC containers.

### AdGuard Secondary

- **Startup:** `order=1, onboot=1`
- **URL:** `adguard-secondary.home.seudominio.com`
- **Installed via:** [community-scripts.org](https://community-scripts.org/scripts/adguard)

Secondary DNS. Synced automatically by AdGuard Home Sync.

### Tailscale (secondary node)

Keeps Tailscale access to the secondary node independent of the main server — useful for managing/powering on the rest of the infra remotely even when the main server is off.

### UPSnap (Wake on LAN)

- **Port:** `8090`
- **Startup:** `order=1, onboot=1`
- **URL:** `upsnap.home.seudominio.com`
- **Service:** `upsnap.service` (systemd)
- **Login:** PocketBase account (administrator email)

Web UI for powering on devices via Wake on LAN.

Register each device (name, IP, MAC) in the UPSnap UI. Get the MAC with `ip link show <interface>` on the target host.

#### Alexa integration (Remote Relay)

Voice WoL works through **Remote Relay** (run the agent on an always-on host, e.g. the secondary Proxmox node). Register the MACs on the Remote Relay device; a single command wakes every MAC on that device.

> One device with multiple MACs → *"Alexa, liga o Homelab"* ("turn on the Homelab") wakes all machines at once.

> SimpleWOL (alternative skill) does **not** work for Linux — it relies on the Echo sending the packet on the local network, with no compatible agent. Remote Relay is the option for Linux hosts.

#### Requirement: enable WoL on the target device

On the node to be powered on remotely, check and enable WoL:

```bash
# Check support and status
ethtool <interface> | grep -i wake

# Enable (e.g. enp1s0)
ethtool -s <interface> wol g
```

To persist across reboots, create a systemd service:

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

> Adjust `<interface>` (check with `ip link`) and `<hostname>` for the target node. The BIOS usually ships with WoL/PME enabled — it only needs to be enabled in the OS via `ethtool`.

#### Creating the UPSnap LXC from scratch (without community scripts)

```bash
# 1. Check available templates on the node
pveam list local

# 2. Create the LXC
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

# 3. Enable nesting and start
pvesh set /nodes/<node>/lxc/<ID>/config --features nesting=1
pct start <ID>

# 4. Install UPSnap
pct exec <ID> -- bash -c "
  apt-get update -qq && apt-get install -y curl unzip &&
  curl -fsSL https://github.com/seriousm4x/UpSnap/releases/download/5.3.5/UpSnap_5.3.5_linux_amd64.zip -o /tmp/upsnap.zip &&
  mkdir -p /opt/upsnap && unzip -q /tmp/upsnap.zip -d /opt/upsnap &&
  chmod +x /opt/upsnap/upsnap
"

# 5. Create the systemd service
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
**Port:** `8765`  
**Public URL:** `mcp.seudominio.com/mcp`  
**Local URL:** `mcp.home.seudominio.com/mcp`

MCP (Model Context Protocol) server that exposes homelab control tools to AI assistants (Claude, etc.).

### Available tools

| Category | Tools |
|---|---|
| Docker | `docker_list_containers`, `docker_container_action`, `docker_container_logs`, `docker_logs_grep`, `docker_container_stats`, `docker_exec_command`, `docker_container_env` |
| SSH | `ssh_exec`, `ssh_read_file`, `ssh_list_dir` |
| Traefik | `traefik_list_routes` |
| Health | `check_service_health` |
| Proxmox | `proxmox_node_status`, `proxmox_node_action`, `proxmox_list_vms`, `proxmox_vm_action`, `proxmox_vm_config`, `proxmox_vm_detach_disk`, `proxmox_vm_resize_disk`, `proxmox_vm_snapshot`, `proxmox_vm_list_snapshots`, `proxmox_vm_rollback`, `proxmox_backup_status`, `proxmox_list_all_backups`, `proxmox_storage_status` |

### Available SSH hosts

Configured via environment variables:

| Variable | Target host | User |
|---|---|---|
| `SSH_HOST_HOMELAB` + `SSH_USER` | Main server | local user |
| `PROXMOX_NODE1_IP` | Primary Proxmox node | `root` |
| `PROXMOX_NODE2_IP` | Secondary Proxmox node | `root` |

SSH key mounted at `/root/.ssh` inside the container (volume `~/.ssh:/root/.ssh:ro`).

### OAuth authentication (Claude.ai)

The server implements OAuth 2.0 Authorization Code + PKCE for Claude.ai remote connectors. The bearer token is set via `MCP_AUTH_TOKEN` in `.env`.

### Build and deploy

```bash
# Build the image
docker build -t mcp-ssh-server:latest apps/mcp-ssh-server/

# Deploy via Dockhand (recommended)
# Or manually:
cd apps/mcp-ssh-server
docker compose --env-file .env up -d --force-recreate
```

> After a container restart, you need to reconnect the MCP connector in Claude.ai (the OAuth session expires).

### Connecting in Claude.ai

1. Open `claude.ai` → Settings → Connectors
2. Add a remote connector with URL: `https://mcp.seudominio.com`
3. Authenticate via OAuth (automatic flow)
4. Enable the connector in the conversation (toggle in the tools panel)

---

## Maintenance Scripts

Located in `apps/scripts/`.

### backup-apps.sh

Creates a compressed backup of `/home/<user>/apps/` with a retention policy and syncs it to Google Drive via rclone.

**Retention policy:**
- 3 most recent backups
- 1 backup that is 7+ days old

**Dependencies:**
- rclone configured and authenticated with Google Drive

```bash
# Run manually
bash apps/scripts/backup-apps.sh

# Schedule via cron (e.g. daily at 2am)
0 2 * * * /path/to/homelab/apps/scripts/backup-apps.sh
```

### docker-cleanup.sh

Removes old Docker images (not `latest`, not in use). Keeps images tagged `latest` and images used by running or stopped containers.

```bash
bash apps/scripts/docker-cleanup.sh
```

---

## Resource Limits

Every service has CPU and memory limits set via `deploy.resources.limits` in the compose file (honored by `docker compose up`, no swarm needed):

```yaml
  radarr:
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1g
```

**How to size them:** limits should come from each container's **real peak**, not guesswork. With the monitoring stack running, query the peak in Prometheus:
```promql
max_over_time(netdata_cgroup_mem_usage_MiB_average[30d])   # memory peak
max_over_time(netdata_cgroup_cpu_percentage_average[30d])  # CPU peak (100% = 1 core)
```
Set `limit ≈ peak × 1.5`.

> **Careful:** exceeding the memory limit → container gets **OOM killed**. Be generous with services that have legitimate spikes (media transcoding, torrent hashing, DB). CPU limits never kill — they only throttle.

> Limits protect against one container monopolizing the host (runaway); they **don't reduce total work** (so they are not a fix for heat — for that, reduce the work itself, e.g. Netdata tuning).

---

## Optional Proxmox Node Optimizations

### Resilient USB Disk Passthrough

When a VM uses USB disk passthrough (`scsiN: /dev/disk/by-id/usb-...`), the disk may disconnect and the VM fails to start (QEMU doesn't support `nofail` on passthrough). A script + systemd service + udev rules manage the disk automatically.

| Component | Role |
|---|---|
| Script (`/usr/local/bin/check-usb-disk-<vmid>.sh`) | Adds/removes the disk from the config depending on presence |
| Systemd service (`Before=pve-guests.service`) | Runs at boot before the VMs |
| udev rules (`ACTION add/remove`) | Reattaches/removes at runtime |

| Scenario | Behavior |
|---|---|
| Boot without disk | Removes `scsiN` from the config → VM starts |
| Boot with disk | Ensures `scsiN` is in the config |
| Disconnects at runtime | udev removes `scsiN` |
| Reconnects at runtime | udev reattaches `scsiN` |

> `qm set --delete scsiN` only removes the reference from the config — it **does not erase data on the disk**. Ready-made examples in `apps/scripts/` (adapt the VMID, disk serial and interface).

### CPU Governor (power / heat savings)

Proxmox uses the `performance` governor by default (prioritizes VM latency), locking the CPU at high frequency even when idle. For 24/7 nodes, `powersave` (`intel_pstate` driver) reduces power draw and heat — it scales dynamically: drops at idle, ramps up under load (burst preserved).

```bash
# Check the current governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# Apply at runtime (reversible)
echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

To persist across reboots, create a systemd service (`cpu-governor.service`) that applies it at boot:

```ini
# /etc/systemd/system/cpu-governor.service
[Unit]
Description=Set CPU governor to powersave
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

> `powersave` on `intel_pstate` does **not** lock to the minimum frequency — it is dynamic (unlike the old acpi-cpufreq governor).

---

## External Access

### Via Cloudflare Tunnel (public)

Selected services are exposed publicly through the tunnel. Choose which services use the `tunnel` entrypoint via labels in the compose file.

### Via Tailscale (private)

Any device on the Tailscale mesh can reach every `*.home.seudominio.com` service as if it were on the local network.

**Client setup:**
1. Install Tailscale on the device
2. Log in with the same account
3. Enable use of the advertised routes in the Tailscale admin panel
4. Configure Tailscale DNS to use AdGuard as the nameserver

---

## Environment Variables

Each stack has a `.env.example` with all required variables. The real `.env` is gitignored — configure it via the Dockhand UI or locally for testing.

| Stack | Main vars |
|---|---|
| `traefik` | `CF_DNS_API_TOKEN`, `CLOUDFLARE_TUNNEL_TOKEN`, domains, service IPs |
| `dashboard` | API keys for every service, `PROXMOX_TOKEN_SECRET` |
| `arrs-stack` | Domains for the arr services |
| `mcp-ssh-server` | `MCP_AUTH_TOKEN`, `MCP_PUBLIC_DOMAIN`, `PROXMOX_TOKEN_SECRET`, `SSH_USER`, `SSH_HOST_HOMELAB` |
| `tailscale` | `TS_AUTHKEY` |
