# Traefik + Cloudflare Tunnel

Reverse proxy com HTTPS automático via Cloudflare DNS challenge e acesso externo sem abrir portas no roteador.

## Pré-requisitos

- Docker e Docker Compose instalados
- Domínio gerenciado pela Cloudflare
- Conta Cloudflare (plano free suficiente)

## Configuração inicial

### 1. Rede Docker

```bash
docker network create traefik
```

### 2. Arquivo acme.json

```bash
touch acme.json && chmod 600 acme.json
```

### 3. Variáveis de ambiente

Copie o `.env.example` para `.env` e preencha os valores:

```bash
cp .env.example .env
```

#### CF_DNS_API_TOKEN

Token da API do Cloudflare com permissão de editar DNS (necessário para emitir certificados Let's Encrypt via DNS challenge).

1. Acesse [dash.cloudflare.com](https://dash.cloudflare.com) → My Profile → API Tokens
2. Create Token → Edit zone DNS (template)
3. Cole o token gerado no `.env`

#### CLOUDFLARE_TUNNEL_TOKEN

Token do Cloudflare Tunnel (permite acesso externo sem abrir portas no roteador).

1. Acesse [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → Networks → Tunnels
2. Create a tunnel → Cloudflared → dê um nome
3. Copie o token exibido no comando `--token` e cole no `.env`
4. Na aba **Rotas** do tunnel, adicione um aplicativo publicado:
   - Hostname: `traefik.seudominio.com`
   - Serviço: `http://traefik:8080`

#### TRAEFIK_BASIC_AUTH

Hash bcrypt da senha do dashboard. Gere com:

```bash
docker run --rm httpd:alpine htpasswd -nbB admin 'suasenha'
```

Escape os `$` trocando cada `$` por `$$` antes de colar no `.env`. Exemplo:

```
# saída do comando:
admin:$2y$05$abc...

# no .env:
TRAEFIK_BASIC_AUTH=admin:$$2y$$05$$abc...
```

### 4. Ajustar caminhos no docker-compose.yaml

Substitua `/home/antony/apps/traefik` pelo caminho absoluto onde os arquivos estão na sua máquina.

### 5. Ajustar domínio

Substitua `traefik.tonho.app.br` pelo seu domínio nos labels do `docker-compose.yaml` e no `traefik.yml` (campo `email`).

## Subir os serviços

```bash
docker compose up -d
```

## Expor um novo serviço

Adicione estas labels no `docker-compose.yaml` do serviço desejado:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.NOME.rule=Host(`subdominio.seudominio.com`)"
  - "traefik.http.routers.NOME.entrypoints=websecure"
  - "traefik.http.routers.NOME.tls.certresolver=cloudflare"
  - "traefik.docker.network=traefik"
networks:
  traefik:
    external: true
```

Para expor pelo Cloudflare Tunnel, adicione também a rota em **Networks → Tunnels → Rotas**:
- Hostname: `subdominio.seudominio.com`
- Serviço: `http://traefik:8080`

E adicione um segundo router no serviço para o entrypoint tunnel:

```yaml
  - "traefik.http.routers.NOME-tunnel.rule=Host(`subdominio.seudominio.com`)"
  - "traefik.http.routers.NOME-tunnel.entrypoints=tunnel"
```
