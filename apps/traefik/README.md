# Traefik + Cloudflare Tunnel

Reverse proxy with automatic HTTPS via Cloudflare DNS challenge, plus external access without opening ports on the router.

## Prerequisites

- Docker and Docker Compose installed
- Domain managed by Cloudflare
- Cloudflare account (free plan is enough)

## Initial setup

### 1. Docker network

```bash
docker network create traefik
```

### 2. acme.json file

```bash
touch acme.json && chmod 600 acme.json
```

### 3. Environment variables

Copy `.env.example` to `.env` and fill in the values:

```bash
cp .env.example .env
```

#### CF_DNS_API_TOKEN

Cloudflare API token with permission to edit DNS (required to issue Let's Encrypt certificates via DNS challenge).

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → My Profile → API Tokens
2. Create Token → Edit zone DNS (template)
3. Paste the generated token into `.env`

#### CLOUDFLARE_TUNNEL_TOKEN

Cloudflare Tunnel token (allows external access without opening ports on the router).

1. Go to [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → Networks → Tunnels
2. Create a tunnel → Cloudflared → give it a name
3. Copy the token shown in the `--token` command and paste it into `.env`
4. In the tunnel's **Routes** tab, add a published application:
   - Hostname: `traefik.seudominio.com`
   - Service: `http://traefik:8080`

#### TRAEFIK_BASIC_AUTH

Bcrypt hash of the dashboard password. Generate it with:

```bash
docker run --rm httpd:alpine htpasswd -nbB admin 'yourpassword'
```

Escape the `$` signs by replacing each `$` with `$$` before pasting into `.env`. Example:

```
# command output:
admin:$2y$05$abc...

# in .env:
TRAEFIK_BASIC_AUTH=admin:$$2y$$05$$abc...
```

### 4. Adjust paths in docker-compose.yaml

Replace `/home/antony/apps/traefik` with the absolute path where the files live on your machine.

### 5. Adjust the domain

Replace `traefik.tonho.app.br` with your domain in the `docker-compose.yaml` labels and in `traefik.yml` (`email` field).

## Start the services

```bash
docker compose up -d
```

## Exposing a new service

Add these labels to the desired service's `docker-compose.yaml`:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.NAME.rule=Host(`subdomain.seudominio.com`)"
  - "traefik.http.routers.NAME.entrypoints=websecure"
  - "traefik.http.routers.NAME.tls.certresolver=cloudflare"
  - "traefik.docker.network=traefik"
networks:
  traefik:
    external: true
```

To expose it through the Cloudflare Tunnel, also add the route under **Networks → Tunnels → Routes**:
- Hostname: `subdomain.seudominio.com`
- Service: `http://traefik:8080`

And add a second router to the service for the tunnel entrypoint:

```yaml
  - "traefik.http.routers.NAME-tunnel.rule=Host(`subdomain.seudominio.com`)"
  - "traefik.http.routers.NAME-tunnel.entrypoints=tunnel"
```
