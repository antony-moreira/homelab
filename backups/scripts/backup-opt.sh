#!/bin/bash

# Caminhos e variáveis
PASTA_ORIGEM="/opt"
NOME_ARQUIVO="opt_backup_$(date +%Y%m%d_%H%M%S).tar"
PASTA_TEMP="/home/homelab/backup"
PASTA_DESTINO="/srv/dev-disk-by-uuid-8e6337d5-7ccf-45db-9be7-8308e9737ca7/Homelab/SYNCTHING"
LOG_FILE="/var/log/backup_opt.log"
TAR_LOG="/var/log/backup_tar.log"

# Lista de exclusões (relativas à PASTA_ORIGEM)
EXCLUIR=(
  "--exclude=grafana*"
  "--exclude=prometheus*"
)

# Função para logar mensagens
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Verifica se a pasta de origem existe
if [ ! -d "$PASTA_ORIGEM" ]; then
  log "Erro: A pasta de origem '$PASTA_ORIGEM' não existe."
  exit 1
fi

# Verifica se a pasta temporária existe
if [ ! -d "$PASTA_TEMP" ]; then
  log "Criando pasta temporária: $PASTA_TEMP"
  mkdir -p "$PASTA_TEMP"
  if [ $? -ne 0 ]; then
    log "Erro ao criar a pasta temporária."
    exit 1
  fi
fi

# Busca por arquivos e pastas que contêm "backup" no nome
log "Procurando arquivos e pastas com o nome 'backup' em '$PASTA_ORIGEM'..."
ARQUIVOS_BACKUP=$(find "$PASTA_ORIGEM" -name "*backup*")

if [ -z "$ARQUIVOS_BACKUP" ]; then
  log "Nenhum arquivo ou pasta com 'backup' encontrado em '$PASTA_ORIGEM'."
  exit 1
fi

# Criação do arquivo compactado com exclusões, incluindo apenas arquivos e pastas com 'backup'
log "Iniciando a compactação dos arquivos e pastas encontrados com 'backup' no nome..."
tar -cvf "$PASTA_TEMP/$NOME_ARQUIVO" "${EXCLUIR[@]}" $ARQUIVOS_BACKUP > "$TAR_LOG" 2>&1

if [ $? -ne 0 ]; then
  log "Erro ao compactar os arquivos. Verifique o arquivo de log: $TAR_LOG"
  exit 1
fi

log "Arquivo compactado criado: $PASTA_TEMP/$NOME_ARQUIVO"

# Movendo o arquivo para o destino
log "Movendo o arquivo compactado para '$PASTA_DESTINO'..."
mv "$PASTA_TEMP/$NOME_ARQUIVO" "$PASTA_DESTINO" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
  log "Erro ao mover o arquivo para '$PASTA_DESTINO'."
  exit 1
fi

log "Backup da pasta '/opt' concluído com sucesso!"
log "Arquivo criado: $PASTA_DESTINO/$NOME_ARQUIVO"