from fastapi import APIRouter

from app.api.routes import health, excel_export, orders, labels

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(excel_export.router)
api_router.include_router(orders.router)
api_router.include_router(labels.router)
