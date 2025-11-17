from os import path
from fastapi import Response

def serve_html(filename: str, prefix: str = "frontend"):
    with open(path.join(prefix, filename), "r") as file:
        return Response(content=file.read(), media_type="text/html")