#!/bin/bash
# Radarr → Telegram notification (Custom Script)
# Configurar em Radarr: Settings → Connect → Custom Script → Path: /config/notify-telegram.sh
# Triggers: On Import (onDownload), On Upgrade
#
# IMPORTANTE: substituir token/chat_id pelos valores reais ao copiar para o servidor.
# No servidor fica em: /home/antony/apps/radarr/notify-telegram.sh (montado como /config no container)
BOT_TOKEN="SEU_BOT_TOKEN"
CHAT_ID="SEU_CHAT_ID"

MESSAGE="🎬 *Filme disponível: ${radarr_movie_title} (${radarr_movie_year})*
📁 Qualidade: ${radarr_moviefile_quality}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="Markdown" \
  -d text="${MESSAGE}"
