from pydantic import BaseModel
import json


class Config(BaseModel):
    cloudflare_zone_id: str
    cloudflare_auth_email: str
    cloudflare_auth_key: str
    turnstile_site_key: str
    turnstile_secret_key: str
    preserved_addresses: list[str]


def load_config():
    with open("config.env.json", "r") as f:
        secrets = json.load(f)
    with open("config.preserved_addresses.json", "r") as f:
        preserved_addresses = json.load(f)
    return Config(**secrets, **preserved_addresses)
