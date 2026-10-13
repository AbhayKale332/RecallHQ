"""Generate an importable Slack manifest for a public HTTPS API URL."""

from urllib.parse import urlsplit

SCOPES = ["commands", "chat:write", "channels:read", "channels:history",
          "groups:read", "groups:history", "users:read"]
EVENTS = ["message.channels", "message.groups", "member_joined_channel", "member_left_channel",
          "channel_rename", "group_rename", "channel_archive", "group_archive",
          "channel_deleted", "group_deleted", "app_uninstalled", "tokens_revoked"]


def manifest(base_url: str) -> dict:
    url = urlsplit(base_url)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Use a public HTTPS URL without credentials, query parameters, or fragments.")
    base_url = base_url.rstrip("/")
    return {
        "display_information": {"name": "RecallHQ", "description": "Ask your team chat. Get cited answers.",
                                "background_color": "#E6176D"},
        "features": {
            "bot_user": {"display_name": "RecallHQ", "always_online": False},
            "slash_commands": [{"command": "/recall", "url": base_url + "/slack/events",
                                "description": "Ask, search, summarize, and catch up on team conversations",
                                "usage_hint": "help | ask <question> | search <terms> | status",
                                "should_escape": True}],
        },
        "oauth_config": {"redirect_urls": [base_url + "/slack/oauth_redirect"], "scopes": {"bot": SCOPES}},
        "settings": {
            "event_subscriptions": {"request_url": base_url + "/slack/events", "bot_events": EVENTS},
            "interactivity": {"is_enabled": True, "request_url": base_url + "/slack/events"},
            "org_deploy_enabled": False, "socket_mode_enabled": False, "token_rotation_enabled": False,
        },
    }
