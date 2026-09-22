from importlib.metadata import version

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from .auth import router as auth_router
from .homework import router as homework_router
from .ics import router as ics_router
from .meetscheule import router as meetschedule_router
from .platform import router as platform_router
from .qqpush import router as qqpush_router

router = APIRouter()
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(homework_router, prefix="/homework", tags=["homework"])
router.include_router(platform_router, prefix="/platform", tags=["platform"])
router.include_router(qqpush_router, prefix="/qqpush", tags=["qqpush"])
router.include_router(
    meetschedule_router, prefix="/meetschedule", tags=["meetschedule"]
)
router.include_router(ics_router, prefix="/ics", tags=["ics"])


@router.get("/version")
async def get_cquptddl_version():
    return PlainTextResponse(version("cquptddl"))
