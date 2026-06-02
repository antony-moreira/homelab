#!/usr/bin/env python3
"""
Bootstrap Uptime Kuma monitors from homelab stack structure.
Run once after initial deployment or to reset monitors.

Usage:
    pip install uptime-kuma-api
    python3 bootstrap-monitors.py --url https://uptime-kuma.home.tonho.app.br \
        --user admin --password yourpassword \
        [--telegram-token TOKEN --telegram-chat-id CHAT_ID]
"""

import argparse
from uptime_kuma_api import UptimeKumaApi, MonitorType, NotificationType

# (container_name, display_name)
STACKS = {
    "📥 arrs-stack": [
        ("sonarr",       "📺 sonarr"),
        ("radarr",       "🎬 radarr"),
        ("prowlarr",     "🔍 prowlarr"),
        ("bazarr",       "💬 bazarr"),
        ("overseerr",    "🎯 overseerr"),
        ("homarr",       "🦦 homarr"),
        ("qbittorrent",  "📥 qbittorrent"),
    ],
    "🖥️ dashboard": [
        ("homepage",  "🏠 homepage"),
        ("dashdot",   "📊 dashdot"),
    ],
    "📊 monitoring-stack": [
        ("prometheus",     "🔥 prometheus"),
        ("grafana",        "📈 grafana"),
        ("netdata",        "🌡️ netdata"),
        ("node-exporter",  "🖥️ node-exporter"),
    ],
    "☁️ nextcloud": [
        ("nextcloud",    "☁️ nextcloud"),
        ("nextcloud-db", "🗃️ nextcloud-db"),
    ],
    "🔀 traefik": [
        ("traefik",     "🔀 traefik"),
        ("cloudflared", "🌐 cloudflared"),
    ],
}

# Individual monitors outside stacks
SINGLES = [
    ("dockhand",         "🐳 dockhand"),
    ("filebrowser",      "📁 filebrowser"),
    ("jellyfin",         "🎵 jellyfin"),
    ("plex",             "🎥 plex"),
    ("watchtower",       "👁️ watchtower"),
    ("tailscale",        "🔒 tailscale"),
    ("adguardhome-sync", "🛡️ adguardhome-sync"),
    ("uptime-kuma",      "💚 uptime-kuma"),
    ("mcp-ssh-server",   "🔑 mcp-ssh-server"),
]


def add_docker_monitor(api, display_name, container_name, docker_host_id, parent_id=None, notification_ids=None):
    kwargs = {
        "type": MonitorType.DOCKER,
        "name": display_name,
        "docker_container": container_name,
        "docker_host": docker_host_id,
        "interval": 60,
    }
    if parent_id:
        kwargs["parent"] = parent_id
    if notification_ids:
        kwargs["notification_id_list"] = {str(nid): True for nid in notification_ids}

    result = api.add_monitor(**kwargs)
    print(f"  + {display_name} ({container_name})")
    return result["monitorID"]


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Uptime Kuma monitors")
    parser.add_argument("--url", required=True, help="Uptime Kuma URL")
    parser.add_argument("--user", required=True, help="Admin username")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--telegram-token", help="Telegram bot token")
    parser.add_argument("--telegram-chat-id", help="Telegram chat ID")
    args = parser.parse_args()

    print(f"Connecting to {args.url}...")
    api = UptimeKumaApi(args.url)
    api.login(args.user, args.password)
    print("Logged in.")

    # Add local Docker host
    print("\nAdding Docker host (local socket)...")
    docker_host = api.add_docker_host(
        name="Local",
        dockerType="socket",
        dockerDaemon="/var/run/docker.sock",
    )
    docker_host_id = docker_host["id"]
    print(f"  Docker host ID: {docker_host_id}")

    # Setup Telegram notification if provided
    notification_ids = []
    if args.telegram_token and args.telegram_chat_id:
        print("\nAdding Telegram notification...")
        notif = api.add_notification(
            type=NotificationType.TELEGRAM,
            name="Telegram",
            isDefault=True,
            applyExisting=True,
            telegramBotToken=args.telegram_token,
            telegramChatID=args.telegram_chat_id,
        )
        notification_ids = [notif["id"]]
        print(f"  Telegram notification ID: {notif['id']}")

    # Create stack groups + monitors
    print("\nCreating stack groups and monitors...")
    for stack_name, containers in STACKS.items():
        print(f"\n[{stack_name}]")
        group = api.add_monitor(
            type=MonitorType.GROUP,
            name=stack_name,
        )
        group_id = group["monitorID"]
        for container_name, display_name in containers:
            add_docker_monitor(api, display_name, container_name, docker_host_id, group_id, notification_ids)

    # Create individual monitors
    print("\n[individual]")
    for container_name, display_name in SINGLES:
        add_docker_monitor(api, display_name, container_name, docker_host_id, notification_ids=notification_ids)

    print("\nDone.")
    api.disconnect()


if __name__ == "__main__":
    main()
