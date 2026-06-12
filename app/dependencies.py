import hmac

from fastapi import Request

from app.config import API_TOKEN
from app.utils.errors import LabelError


def check_label_auth(request: Request):
    # Auth is skipped when API_TOKEN is empty (local development).
    if not API_TOKEN:
        return

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise LabelError(401, "Missing Authorization bearer token.")

    candidate = auth_header[7:].strip()
    if hmac.compare_digest(candidate.encode(), API_TOKEN.encode()):
        return

    raise LabelError(401, "Invalid API token.")
