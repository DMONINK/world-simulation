"""
discord_webhook/sender.py — Posts the yearly chronicle (and the eventual
victory finale) to Discord via a plain webhook URL. No bot token, no paid
API — exactly per the brief's free-tier-only constraint.
"""

import requests

import config


def send_discord_update(embed_data: dict):
    url = config.DISCORD_WEBHOOK_URL
    if not url:
        print("[Webhook] DISCORD_WEBHOOK_URL not set — skipping send. "
              "Set it in Replit Secrets to enable Discord updates.")
        return False
    payload = {"embeds": [embed_data]}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code >= 300:
            print(f"[Webhook Error] HTTP {resp.status_code}: {resp.text[:300]}")
            return False
        return True
    except Exception as e:
        print(f"[Webhook Error] {e}")
        return False


def send_yearly_update(embed_dict):
    """embed_dict is the output of narrative.build_yearly_embed() or
    narrative.build_victory_embed() — already shaped as a Discord embed
    (title/description/color/footer)."""
    return send_discord_update(embed_dict)
