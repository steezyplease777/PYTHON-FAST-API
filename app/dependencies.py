import hmac

from fastapi import Request

from app.config import API_TOKEN
from app.utils.errors import LabelError


def check_label_auth(request: Request, body_token: str | None):
    # Auth is skipped when API_TOKEN is empty (local development).
    if not API_TOKEN:
        return

    candidates = []

    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        candidates.append(auth_header[7:].strip())

    if body_token:
        candidates.append(str(body_token))

    for candidate in candidates:
        if hmac.compare_digest(candidate.encode(), API_TOKEN.encode()):
            return

    raise LabelError(401, "Invalid API token.")
