from fastapi import FastAPI

from app.api.router import api_router
from app.dependencies import check_label_auth
from app.utils.errors import LabelError, label_error_response

app = FastAPI()


@app.middleware("http")
async def require_api_auth(request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    try:
        check_label_auth(request)
    except LabelError as e:
        return label_error_response(e.status_code, e.message)

    return await call_next(request)


app.include_router(api_router)
