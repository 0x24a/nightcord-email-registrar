from fastapi import FastAPI
from config import load_config

config = load_config()
app = FastAPI()


@app.get("/api/v1/turnstile_site_key")
async def get_turnstile_site_key():
    return config.turnstile_site_key
