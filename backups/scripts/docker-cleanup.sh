#!/bin/bash

# Habilitar "strict mode" no bash para maior segurança.
set -euo pipefail

# Exibe mensagem inicial
echo "Iniciando limpeza de imagens Docker..."

# Lista os IDs das imagens Docker que não possuem a tag "latest"
imagens_para_remover=$(docker images --format "{{.ID}} {{.Tag}}" | grep -v " latest$" | awk '{print $1}')

# Verifica se há imagens para remover
if [ -z "$imagens_para_remover" ]; then
  echo "Nenhuma imagem para remover."
else
  # Loop para remover cada imagem encontrada
  while IFS= read -r imagem_id; do
    echo "Removendo imagem com ID: $imagem_id"
    docker rmi -f "$imagem_id"
  done <<< "$imagens_para_remover"
  echo "Todas as imagens não-latest foram removidas."
fi

# Finaliza o script
echo "Limpeza concluída."