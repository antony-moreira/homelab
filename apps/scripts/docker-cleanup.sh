#!/bin/bash
set -euo pipefail

echo "$(date '+%Y-%m-%d %H:%M:%S') - Iniciando limpeza de imagens Docker..."

# IDs em uso por qualquer container (rodando ou parado)
in_use_ids=$(docker ps -a --no-trunc --format "{{.ImageID}}" | sort -u)

# IDs que possuem a tag latest (um mesmo ID pode ter multiplas tags)
latest_ids=$(docker images --no-trunc --format "{{.ID}} {{.Tag}}" | awk '$2 == "latest" {print $1}' | sort -u)

removidas=0
erros=0

while IFS= read -r line; do
  id=$(echo "$line" | awk '{print $1}')
  ref=$(echo "$line" | awk '{print $2":"$3}')

  # Pula se esse ID tambem esta taggeado como latest
  if echo "$latest_ids" | grep -qF "$id"; then
    continue
  fi

  # Pula se em uso por algum container
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

# Limpa imagens dangling (sem tag)
dangling=$(docker images -f "dangling=true" -q | wc -l)
if [ "$dangling" -gt 0 ]; then
  echo "  Removendo $dangling imagem(ns) dangling..."
  docker image prune -f > /dev/null
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Concluido. Removidas: $removidas | Erros: $erros | Dangling: $dangling"
