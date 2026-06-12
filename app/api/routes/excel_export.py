import json
import os
import shutil
import tempfile
import traceback
import zipfile

from fastapi import APIRouter, Form, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.services.excel_service import (
    process_export_job,
    make_square_fill_image,
    cleanup_temp_dir,
)

router = APIRouter()


@router.post("/export")
async def export_excel(
    payload: str = Form(...),
    image_manifest: str = Form(...),
    images_zip: UploadFile = File(...),
):
    temp_dir = tempfile.mkdtemp(prefix="excel_export_")

    try:
        raw = json.loads(payload)
        manifest = json.loads(image_manifest)

        request_body = raw.get("body", raw)
        rows = request_body.get("data")

        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=400, detail='Request must contain "data" as a non-empty array.')

        if not isinstance(manifest, dict):
            raise HTTPException(status_code=400, detail="image_manifest must be a JSON object.")

        zip_path = os.path.join(temp_dir, images_zip.filename or "images.zip")

        with open(zip_path, "wb") as f:
            shutil.copyfileobj(images_zip.file, f)

        extracted_dir = os.path.join(temp_dir, "images")
        os.makedirs(extracted_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)

        image_path_map = {}
        for image_url, filename in manifest.items():
            local_path = os.path.join(extracted_dir, filename)
            if os.path.exists(local_path):
                processed_path = make_square_fill_image(local_path, temp_dir, filename)
                image_path_map[image_url] = processed_path

        public_url = process_export_job(rows, image_path_map, temp_dir)

        return JSONResponse({
            "ok": True,
            "url": public_url,
        })

    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cleanup_temp_dir(temp_dir)
