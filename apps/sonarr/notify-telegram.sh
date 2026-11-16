#!/bin/bash
# Sonarr → Telegram notification (Custom Script)
# Configure in Sonarr: Settings → Connect → Custom Script → Path: /config/notify-telegram.sh
# Triggers: On Import (onDownload), On Upgrade
#
# IMPORTANT: replace token/chat_id with the real values when copying to the server.
# On the server it lives at: /home/antony/apps/sonarr/notify-telegram.sh (mounted as /config in the container)
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
