import asyncio
import base64
import traceback

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from app.config import LABELS_DEFAULT_BUCKET, MAX_BATCH_LABELS
from app.dependencies import check_label_auth
from app.models.labels import LabelPayload, BatchPayload
from app.services.label_service import generate_pdf, validate_upc
from app.services.storage_service import upload_label_pdf
from app.utils.errors import LabelError, label_error_response
from app.utils.formatting import sanitize_path_part, normalize_combined_filename

router = APIRouter()


@router.post("/labels")
async def create_label(request: Request, body: dict = Body(...)):
    try:
        try:
            payload = LabelPayload.model_validate(body)
        except Exception as e:
            return label_error_response(400, f"Invalid request body: {e}")

        check_label_auth(request, payload.token)

        if not payload.productId:
            raise LabelError(400, "productId is required.")

        validate_upc(payload.upc)

        mode = payload.mode.strip().lower()
        if mode not in ("upload", "inline", "download"):
            raise LabelError(400, f"Unsupported mode: {payload.mode}")

        label = {
            "title": payload.title,
            "productId": payload.productId,
            "sku": payload.sku,
            "upc": payload.upc,
            "msrp": payload.msrp,
            "size": payload.size,
        }

        pdf_bytes = await asyncio.to_thread(generate_pdf, [label])
        filename = f"{payload.upc}.pdf"

        if mode == "inline":
            return JSONResponse({
                "ok": True,
                "statusCode": 200,
                "status": "success",
                "mode": "inline",
                "filename": filename,
                "contentType": "application/pdf",
                "pdf_base64": base64.b64encode(pdf_bytes).decode(),
            })

        if mode == "download":
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        bucket = payload.supabase_bucket or LABELS_DEFAULT_BUCKET
        path = payload.supabase_path or f"{sanitize_path_part(payload.productId)}/{payload.upc}.pdf"

        public_url, download_url = await asyncio.to_thread(upload_label_pdf, pdf_bytes, bucket, path)

        return JSONResponse({
            "ok": True,
            "statusCode": 200,
            "status": "success",
            "mode": "upload",
            "url": public_url,
            "downloadUrl": download_url,
            "filePath": path,
            "filename": filename,
            "bucket": bucket,
            "title": payload.title,
            "productId": payload.productId,
            "sku": payload.sku,
            "upc": payload.upc,
            "size": payload.size,
            "msrp": payload.msrp,
        })

    except LabelError as e:
        return label_error_response(e.status_code, e.message)
    except Exception as e:
        print(traceback.format_exc())
        return label_error_response(500, f"Unexpected server error: {e}")


@router.post("/labels/batch")
async def create_labels_batch(request: Request, body: dict = Body(...)):
    try:
        try:
            payload = BatchPayload.model_validate(body)
        except Exception as e:
            return label_error_response(400, f"Invalid request body: {e}")

        check_label_auth(request, payload.token)

        if not payload.variants:
            raise LabelError(400, "variants must be a non-empty array.")

        if len(payload.variants) > MAX_BATCH_LABELS:
            raise LabelError(400, f"Too many variants: {len(payload.variants)} (max {MAX_BATCH_LABELS}).")

        mode = payload.mode.strip().lower()
        if mode not in ("upload", "inline", "download"):
            raise LabelError(400, f"Unsupported mode: {payload.mode}")

        labels = []
        for idx, variant in enumerate(payload.variants):
            if not variant.productId:
                raise LabelError(400, f"variants[{idx}]: productId is required.")
            try:
                validate_upc(variant.upc)
            except LabelError as e:
                raise LabelError(e.status_code, f"variants[{idx}]: {e.message}")

            labels.append({
                "title": variant.title,
                "productId": variant.productId,
                "sku": variant.sku,
                "upc": variant.upc,
                "msrp": variant.msrp,
                "size": variant.size,
            })

        pdf_bytes = await asyncio.to_thread(generate_pdf, labels)

        normalized_title = normalize_combined_filename(payload.title or "LABELS")
        filename = f"{normalized_title}_UPC_LABELS.pdf"

        if mode == "inline":
            return JSONResponse({
                "ok": True,
                "statusCode": 200,
                "status": "success",
                "mode": "inline",
                "filename": filename,
                "contentType": "application/pdf",
                "labelCount": len(labels),
                "pdf_base64": base64.b64encode(pdf_bytes).decode(),
            })

        if mode == "download":
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        bucket = payload.supabase_bucket or LABELS_DEFAULT_BUCKET
        path = payload.supabase_path or f"combined/{filename}"

        public_url, download_url = await asyncio.to_thread(upload_label_pdf, pdf_bytes, bucket, path)

        return JSONResponse({
            "ok": True,
            "statusCode": 200,
            "status": "success",
            "mode": "upload",
            "url": public_url,
            "downloadUrl": download_url,
            "filePath": path,
            "filename": filename,
            "bucket": bucket,
            "title": payload.title,
            "labelCount": len(labels),
        })

    except LabelError as e:
        return label_error_response(e.status_code, e.message)
    except Exception as e:
        print(traceback.format_exc())
        return label_error_response(500, f"Unexpected server error: {e}")
