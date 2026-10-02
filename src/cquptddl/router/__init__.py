from fastapi import APIRouter

from cquptddl import core

from .api import router as api_router

router = APIRouter()
router.include_router(api_router, prefix="/api")

if core.config.FRONTEND_DIR:
    router.frontend("/", directory=core.config.FRONTEND_DIR, fallback="index.html")
