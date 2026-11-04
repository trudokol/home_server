import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings():
    owner_id : int
    telegram_token : str
    is_telegram_blocked : bool
    mqtt_broker : str | None
    mqtt_port : int | None
    mqtt_username : str | None
    mqtt_password : str | None
    heartbeat_endpoint : str | None
    debug_mode : bool

def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        owner_id = int(os.environ["OWNER_ID"]),
        telegram_token = os.environ["TOKEN"],
        is_telegram_blocked = bool(os.environ["BLOCKED"]),
        mqtt_broker = os.environ.get("MQTT_BROKER") or None,
        mqtt_port = int(os.environ.get("MQTT_PORT")) or None,
        mqtt_username = os.environ.get("MQTT_USERNAME") or None,
        mqtt_password = os.environ.get("MQTT_PASSWORD") or None,
        heartbeat_endpoint = os.environ.get("HEARTBEAT_ENDPOINT") or None,
        debug_mode = os.environ["DEBUG"]
    )