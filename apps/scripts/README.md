# Scripts

Homelab maintenance scripts. On the server they live in `/home/antony/apps/scripts/`.

---

## backup-apps.sh

Compresses `/home/antony/apps` into a `.tar.gz` and applies a retention policy.

**Usage:**
```bash
./backup-apps.sh
```

**Behavior:**
- Destination: `/home/antony/backup/`
- Format: `apps_backup_YYYYMMDD.tar.gz`
- Excludes: `grafana`, `prometheus`
- Doesn't create a duplicate if it already ran today

**Retention:**
- 3 most recent backups (daily)
- 1 backup that is >= 7 days old (the closest one to 7 days available)

**Log:** `/var/log/backup_apps.log`

**Cron:** daily at 03:00
```
0 3 * * * /home/antony/apps/scripts/backup-apps.sh >> /var/log/backup_apps.log 2>&1
```

After local retention, the script automatically syncs to Google Drive via rclone (see setup below).

---

## rclone setup (Google Drive)

Only needed once. Requires a browser on the local machine.

**1. Install rclone locally:**
```bash
curl https://rclone.org/install.sh | sudo bash
```

**2. Authenticate with Google Drive:**
```bash
rclone config
```

Wizard answers:
- `n` → new remote
- name: `gdrive`
- storage: the number for **Google Drive** in the list
- client_id / client_secret: Enter (empty)
- scope: `1` (full access)
- root_folder_id / service_account_file: Enter (empty)
- Edit advanced: `n`
- auto config: `y` → opens browser → log in → authorize
- shared drive: `n`
- confirm: `y` → `q`

**3. Copy the config to the server:**
```bash
ssh antony@192.168.3.110 "mkdir -p /home/antony/apps/rclone"
scp ~/.config/rclone/rclone.conf antony@192.168.3.110:/home/antony/apps/rclone/rclone.conf
```

**4. Test the connection on the server:**
```bash
ssh antony@192.168.3.110
docker run --rm \
  -v /home/antony/apps/rclone/rclone.conf:/config/rclone/rclone.conf:ro \
  rclone/rclone lsd gdrive:
```

It should list your Google Drive folders.

> `rclone.conf` contains an OAuth token — it is in `.gitignore` and **must never go to the repository**.

---

## docker-cleanup.sh

Removes Docker images that are not tagged `latest` and are not used by any container.

**Usage:**
```bash
./docker-cleanup.sh
```

**Behavior:**
- Skips images whose ID also has the `latest` tag
- Skips images used by containers (running or stopped)
- Removes dangling (untagged) images via `docker image prune`

**Log:** `/var/log/docker-cleanup.log`

**Cron:** every Thursday at 05:00
```
0 5 * * 4 /home/antony/apps/scripts/docker-cleanup.sh >> /var/log/docker-cleanup.log 2>&1
```
