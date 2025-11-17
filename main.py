from fastapi import FastAPI, Request
from config import load_config
from httpx import AsyncClient
from utils import serve_html, SignupSession
import re
import uuid

config = load_config()
app = FastAPI()
sessions: dict[str, SignupSession] = {}


@app.get("/api/v1/get_turnstile_site_key")
async def get_turnstile_site_key():
    return {"site_key": config.turnstile_site_key}


@app.get("/api/v1/get_preserved_addresses")
async def get_preserved_addresses():
    return {"preserved_addresses": config.preserved_addresses}


@app.post("/api/v1/register")
async def register(request: Request):
    async with AsyncClient() as client:
        data = await request.json()
        response = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            json={
                "secret": config.turnstile_secret_key,
                "response": data["turnstile_token"],
            },
        )
        if not response.json()["success"]:
            return {"error": 10006}
        # verify e-mail address with regex
        if not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]):
            return {"error": 10001}
        if data['email'].endswith("@nightcord.email"):
            return {"error":10008}
        # check local part
        if not re.match(r"^[a-zA-Z0-9._-]+", data["username"]):
            return {"error": 10003}
        # check if username is preserved
        if data["username"] in config.preserved_addresses:
            return {"error": 10005}
        # check count
        number = (await client.get(f"https://api.cloudflare.com/client/v4/accounts/{config.cloudflare_account_id}/email/routing/addresses", headers={
            "Authorization": f"Bearer {config.cloudflare_auth_key}"
        })).json().get("result_info", {}).get("total_count", -1)
        print(f"Current count: {number}")
        if number >= config.max_addresses:
            return {"error": 10000}
        # check if e-mail already exists
        # first check in cache
        for i in sessions.values():
            if i.email == data["email"]:
                return {"error": 10002}

        emails_found = (
            await client.get(
                f"https://api.cloudflare.com/client/v4/accounts/{config.cloudflare_account_id}/email/routing/addresses",
                params={
                    "order": "created",
                    "direction": "asc",
                    "page": 1,
                    "per_page": 25,
                    "q": data["email"],
                },
                headers={
                    "Authorization": f"Bearer {config.cloudflare_auth_key}",
                },
            )
        ).json()
        print(emails_found)
        email_exists = emails_found.get("result_info", {}).get("total_count", 0) != 0
        if email_exists:
            return {"error": 10002}
        # check if username exists
        # first check in cache
        for i in sessions.values():
            if i.email == data["email"]:
                return {"error": 10004}
        username_found = (
            await client.get(
                f"https://api.cloudflare.com/client/v4/zones/{config.cloudflare_zone_id}/email/routing/rules",
                params={
                    "order": "created",
                    "direction": "asc",
                    "page": 1,
                    "per_page": 25,
                    "q": data["username"] + "@nightcord.email",
                    "matcher.type": "literal",
                },
                headers={
                    "Authorization": f"Bearer {config.cloudflare_auth_key}",
                },
            )
        ).json()
        print(username_found)
        username_exists = (
            username_found.get("result_info", {}).get("total_count", 0) != 0
        )
        if username_exists:
            return {"error": 10004}
        # send confirmation email
        confirm_result = (
            await client.post(
                f"https://api.cloudflare.com/client/v4/accounts/{config.cloudflare_account_id}/email/routing/addresses",
                json={"email": data["email"]},
                headers={
                    "Authorization": f"Bearer {config.cloudflare_auth_key}",
                },
            )
        ).json()
        if confirm_result.get("success", False):
            sessionid = uuid.uuid4().hex
            sessions[sessionid] = SignupSession(
                email=data["email"], username=data["username"], tries_left=3
            )
            return {"error": 0, "session": sessionid}
        else:
            print(confirm_result)
            return {"error": 10007}

@app.get("/api/v1/finish_apply")
async def finish_apply_api(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return {"error": 20001}
    if session.tries_left <= 0:
        del sessions[session_id]
        return {"error": 20002}
    async with AsyncClient() as client:
        verified_request = (
            await client.get(
                f"https://api.cloudflare.com/client/v4/accounts/{config.cloudflare_account_id}/email/routing/addresses",
                params={
                    "order": "created",
                    "direction": "asc",
                    "page": 1,
                    "per_page": 25,
                    "q": session.email,
                },
                headers={
                    "Authorization": f"Bearer {config.cloudflare_auth_key}",
                },
            )
        ).json()
        print(verified_request)
        if not verified_request.get("success", False):
            sessions[session_id] = SignupSession(
                email=session.email,
                username=session.username,
                tries_left=session.tries_left - 1,
            )
            return {"error": 20003}
        if verified_request.get("result_info",{}).get("total_count", 0) != 1:
            sessions[session_id] = SignupSession(
                email=session.email,
                username=session.username,
                tries_left=session.tries_left - 1,
            )
            return {"error": 20004}
        if verified_request.get("result", [{}])[0].get("verified", None) is None:
            sessions[session_id] = SignupSession(
                email=session.email,
                username=session.username,
                tries_left=session.tries_left - 1,
            )
            return {"error": 20005}
        create_request = (await client.post(
            f"https://api.cloudflare.com/client/v4/zones/{config.cloudflare_zone_id}/email/routing/rules",
            headers={
                "Authorization": f"Bearer {config.cloudflare_auth_key}",
            },
            json={
              "enabled": True,
              "name": "Rule created by Nightcord Email Registrar",
              "actions": [
                {
                  "type": "forward",
                  "value": [
                    session.email
                  ]
                }
              ],
              "matchers": [
                {
                  "type": "literal",
                  "field": "to",
                  "value": f"{session.username}@nightcord.email"
                }
              ]
            }
        )).json()
        if not create_request.get('success', False):
            sessions[session_id] = SignupSession(
                email=session.email,
                username=session.username,
                tries_left=session.tries_left - 1,
            )
            return {"error": 20006}
        return {'error':0}
        
        

@app.get("/")
async def main():
    return serve_html("index.html")

@app.get('/finish-apply')
async def finish_apply():
    return serve_html("finish-apply.html")
