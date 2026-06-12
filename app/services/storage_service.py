import time
from urllib.parse import quote

import requests

from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET
from app.utils.errors import LabelError
from app.utils.formatting import encode_storage_path

SESSION = requests.Session()


def upload_xlsx_to_supabase(file_path: str, filename: str) -> str:
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "x-upsert": "false",
    }

    with open(file_path, "rb") as f:
        response = SESSION.post(upload_url, headers=headers, data=f, timeout=(5, 120))

    if response.status_code not in (200, 201):
        raise Exception(f"Supabase upload failed: {response.status_code} {response.text}")

    return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"


def upload_label_pdf(pdf_bytes: bytes, bucket: str, path: str) -> tuple[str, str]:
    if not SUPABASE_SERVICE_ROLE_KEY:
        raise LabelError(500, "Missing SUPABASE_SERVICE_ROLE_KEY.")

    encoded_path = encode_storage_path(path)
    upload_url = f"{SUPABASE_URL}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"

    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }

    response = SESSION.post(upload_url, headers=headers, data=pdf_bytes, timeout=(5, 30))

    if response.status_code not in (200, 201):
        raise LabelError(502, f"Supabase upload failed: {response.status_code} {response.text}")

    timestamp = int(time.time() * 1000)
    filename = path.split("/")[-1]
    base = f"{SUPABASE_URL}/storage/v1/object/public/{quote(bucket, safe='')}/{encoded_path}"

    public_url = f"{base}?t={timestamp}"
    download_url = f"{base}?download={quote(filename, safe='')}&t={timestamp}"

    return public_url, download_url
