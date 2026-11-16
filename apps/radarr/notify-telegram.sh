#!/bin/bash
# Radarr → Telegram notification (Custom Script)
# Configure in Radarr: Settings → Connect → Custom Script → Path: /config/notify-telegram.sh
# Triggers: On Import (onDownload), On Upgrade
#
# IMPORTANT: replace token/chat_id with the real values when copying to the server.
# On the server it lives at: /home/antony/apps/radarr/notify-telegram.sh (mounted as /config in the container)
BOT_TOKEN="SEU_BOT_TOKEN"
CHAT_ID="SEU_CHAT_ID"

MESSAGE="🎬 *Filme disponível: ${radarr_movie_title} (${radarr_movie_year})*
📁 Qualidade: ${radarr_moviefile_quality}"

curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="${CHAT_ID}" \
  -d parse_mode="Markdown" \
  -d text="${MESSAGE}"
