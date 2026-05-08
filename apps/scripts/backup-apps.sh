#!/bin/bash
set -euo pipefail

PASTA_ORIGEM="/home/antony/apps"
PASTA_DESTINO="/home/antony/backup"
LOG_FILE="/var/log/backup_apps.log"
NOME_ARQUIVO="apps_backup_$(date +%Y%m%d).tar.gz"

EXCLUIR=(
  "--exclude=grafana"
  "--exclude=prometheus"
)

MANTER_RECENTES=3
MANTER_SEMANA_DIAS=7
RCLONE_CONFIG="/home/antony/apps/rclone/rclone.conf"
GDRIVE_DESTINO="gdrive:homelab-backup"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

mkdir -p "$PASTA_DESTINO"

if [ ! -d "$PASTA_ORIGEM" ]; then
  log "ERRO: pasta de origem '$PASTA_ORIGEM' nao existe."
  exit 1
fi

# Evita criar duplicata se ja rodou hoje
if [ -f "$PASTA_DESTINO/$NOME_ARQUIVO" ]; then
  log "Backup de hoje ja existe: $NOME_ARQUIVO — abortando."
  exit 0
fi

log "Iniciando backup de $PASTA_ORIGEM..."
tar --ignore-failed-read -czf "$PASTA_DESTINO/$NOME_ARQUIVO" "${EXCLUIR[@]}" -C "$(dirname "$PASTA_ORIGEM")" "$(basename "$PASTA_ORIGEM")"
log "Backup criado: $PASTA_DESTINO/$NOME_ARQUIVO ($(du -sh "$PASTA_DESTINO/$NOME_ARQUIVO" | cut -f1))"

# --- Retenção ---
log "Aplicando politica de retencao (ultimos $MANTER_RECENTES dias + 1 copia de ${MANTER_SEMANA_DIAS} dias)..."

mapfile -t arquivos < <(ls -t "$PASTA_DESTINO"/apps_backup_????????.tar.gz 2>/dev/null)
total=${#arquivos[@]}

declare -A manter
# Manter os N mais recentes
for (( i=0; i<MANTER_RECENTES && i<total; i++ )); do
  manter["${arquivos[$i]}"]=1
done

# Manter 1 arquivo com >= 7 dias (o mais proximo de 7 dias)
now=$(date +%s)
best_diff=99999
best_file=""
for f in "${arquivos[@]}"; do
  age=$(( (now - $(stat -c %Y "$f")) / 86400 ))
  if [ "$age" -ge "$MANTER_SEMANA_DIAS" ]; then
    diff=$(( age - MANTER_SEMANA_DIAS ))
    if [ "$diff" -lt "$best_diff" ]; then
      best_diff=$diff
      best_file="$f"
    fi
  fi
done
[ -n "$best_file" ] && manter["$best_file"]=1

# Remover o que nao esta na lista de manter
for f in "${arquivos[@]}"; do
  if [ -z "${manter[$f]+x}" ]; then
    log "Removendo backup antigo: $(basename "$f")"
    rm -f "$f"
  fi
done

kept=$(ls "$PASTA_DESTINO"/apps_backup_????????.tar.gz 2>/dev/null | wc -l)
log "Retencao aplicada. $kept arquivo(s) mantido(s) localmente."

# --- Sync Google Drive ---
log "Sincronizando com Google Drive ($GDRIVE_DESTINO)..."
if docker run --rm \
  -v "$PASTA_DESTINO":/backup:ro \
  -v "$RCLONE_CONFIG":/config/rclone/rclone.conf:ro \
  rclone/rclone sync /backup "$GDRIVE_DESTINO" --transfers=2 2>>"$LOG_FILE"; then
  log "Sync Google Drive concluido."
else
  log "ERRO: falha no sync com Google Drive."
fi
