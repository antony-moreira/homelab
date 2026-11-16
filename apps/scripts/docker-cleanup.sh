#!/bin/bash
set -euo pipefail

echo "$(date '+%Y-%m-%d %H:%M:%S') - Iniciando limpeza de imagens Docker..."

# IDs in use by any container (running or stopped)
in_use_ids=$(docker ps -a --no-trunc --format "{{.ImageID}}" | sort -u)

# IDs that have the latest tag (the same ID can have multiple tags)
latest_ids=$(docker images --no-trunc --format "{{.ID}} {{.Tag}}" | awk '$2 == "latest" {print $1}' | sort -u)

removidas=0
erros=0

while IFS= read -r line; do
  id=$(echo "$line" | awk '{print $1}')
  ref=$(echo "$line" | awk '{print $2":"$3}')

  # Skip if this ID is also tagged as latest
  if echo "$latest_ids" | grep -qF "$id"; then
    continue
  fi

  # Skip if in use by any container
  if echo "$in_use_ids" | grep -qF "$id"; then
    echo "  Em uso, pulando: $ref"
    continue
  fi

  echo "  Removendo: $ref"
  if docker rmi "$ref" > /dev/null 2>&1; then
    (( removidas++ )) || true
  else
    echo "  AVISO: falha ao remover $ref"
    (( erros++ )) || true
  fi

done < <(docker images --no-trunc --format "{{.ID}} {{.Repository}} {{.Tag}}" | grep -v " latest$" | grep -v " <none>$")

# Clean up dangling (untagged) images
dangling=$(docker images -f "dangling=true" -q | wc -l)
if [ "$dangling" -gt 0 ]; then
  echo "  Removendo $dangling imagem(ns) dangling..."
  docker image prune -f > /dev/null
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Concluido. Removidas: $removidas | Erros: $erros | Dangling: $dangling"
