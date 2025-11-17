from fastapi import FastAPI
from config import load_config
from utils import serve_html

config = load_config()
app = FastAPI()


@app.get("/api/v1/get_turnstile_site_key")
async def get_turnstile_site_key():
    return {"site_key":config.turnstile_site_key}

@app.get("/api/v1/get_preserved_addresses")
async def get_preserved_addresses():
    return {"preserved_addresses":config.preserved_addresses}

@app.get("/")
async def main():
    return serve_html("index.html")