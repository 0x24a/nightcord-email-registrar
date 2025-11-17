from os import path
from fastapi import Response
from pydantic import BaseModel


def serve_html(filename: str, prefix: str = "frontend"):
    with open(path.join(prefix, filename), "r") as file:
        return Response(content=file.read(), media_type="text/html")


class SignupSession(BaseModel):
    username: str
    email: str
    tries_left: int
