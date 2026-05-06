# Scripts

Scripts de manutenção do homelab. No server ficam em `/home/antony/apps/scripts/`.

---

## backup-apps.sh

Compacta `/home/antony/apps` em um `.tar.gz` e aplica política de retenção.

**Uso:**
```bash
./backup-apps.sh
```

**Comportamento:**
- Destino: `/home/antony/backup/`
- Formato: `apps_backup_YYYYMMDD.tar.gz`
- Exclui: `grafana`, `prometheus`
- Não cria duplicata se já rodou hoje

**Retenção:**
- 3 backups mais recentes (diários)
- 1 backup com >= 7 dias (o mais próximo de 7 dias disponível)

**Log:** `/var/log/backup_apps.log`

**Cron:** diário às 03:00
```
0 3 * * * /home/antony/apps/scripts/backup-apps.sh >> /var/log/backup_apps.log 2>&1
```

Após a retenção local, o script sincroniza automaticamente com o Google Drive via rclone (ver configuração abaixo).

---

## Configuração do rclone (Google Drive)

Necessário apenas uma vez. Requer browser na máquina local.

**1. Instalar rclone localmente:**
```bash
curl https://rclone.org/install.sh | sudo bash
```

**2. Autenticar com Google Drive:**
```bash
rclone config
```

Respostas no wizard:
- `n` → new remote
- name: `gdrive`
- storage: número do **Google Drive** na lista
- client_id / client_secret: Enter (vazio)
- scope: `1` (full access)
- root_folder_id / service_account_file: Enter (vazio)
- Edit advanced: `n`
- auto config: `y` → abre browser → loga → autoriza
- shared drive: `n`
- confirma: `y` → `q`

**3. Copiar config pro server:**
```bash
ssh antony@192.168.3.110 "mkdir -p /home/antony/apps/rclone"
scp ~/.config/rclone/rclone.conf antony@192.168.3.110:/home/antony/apps/rclone/rclone.conf
```

**4. Testar conexão no server:**
```bash
ssh antony@192.168.3.110
docker run --rm \
  -v /home/antony/apps/rclone/rclone.conf:/config/rclone/rclone.conf:ro \
  rclone/rclone lsd gdrive:
```

Deve listar as pastas do Google Drive.

> `rclone.conf` contém token OAuth — está no `.gitignore` e **nunca deve ir pro repositório**.

---

## docker-cleanup.sh

Remove imagens Docker que não estão taggeadas como `latest` e não estão em uso por nenhum container.

**Uso:**
```bash
./docker-cleanup.sh
```

**Comportamento:**
- Ignora imagens cujo ID também possui a tag `latest`
- Ignora imagens em uso por containers (rodando ou parados)
- Remove imagens dangling (sem tag) via `docker image prune`

**Log:** `/var/log/docker-cleanup.log`

**Cron:** toda quinta-feira às 05:00
```
0 5 * * 4 /home/antony/apps/scripts/docker-cleanup.sh >> /var/log/docker-cleanup.log 2>&1
```
