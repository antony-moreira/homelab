#!/bin/bash
# Sonarr → Telegram notification (Custom Script)
# Configurar em Sonarr: Settings → Connect → Custom Script → Path: /config/notify-telegram.sh
# Triggers: On Import (onDownload), On Upgrade
#
# IMPORTANTE: substituir token/chat_id pelos valores reais ao copiar para o servidor.
# No servidor fica em: /home/antony/apps/sonarr/notify-telegram.sh (montado como /config no container)
BOT_TOKEN="SEU_BOT_TOKEN"
CHAT_ID="SEU_CHAT_ID"

MESSAGE="📺 *Série disponível: ${sonarr_series_title}*
🗂 Temporada ${sonarr_episodefile_seasonnumber} - Episódio ${sonarr_episodefile_episodenumbers}
🎞 ${sonarr_episodefile_episodetitles}
📁 Qualidade: ${sonarr_episodefile_quality}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="Markdown" \
  -d text="${MESSAGE}"
