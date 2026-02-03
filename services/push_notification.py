"""
OneSignal push notification sender.
"""
import os
import requests

ONESIGNAL_APP_ID = os.getenv("ONESIGNAL_APP_ID")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY")


def send_push(player_ids, heading: str, content: str) -> bool:
    if not (ONESIGNAL_APP_ID and ONESIGNAL_API_KEY):
        return False
    if not player_ids:
        return False
    url = "https://onesignal.com/api/v1/notifications"
    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "include_player_ids": player_ids,
        "headings": {"en": heading},
        "contents": {"en": content},
    }
    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    return resp.status_code == 200
