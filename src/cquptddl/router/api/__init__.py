from fastapi import APIRouter

from .auth import router as auth_router
from .homework import router as homework_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth")
router.include_router(homework_router, prefix="/homework")
