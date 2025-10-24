"""Router package exposing all API routers."""

from fastapi import APIRouter

from .auth.router import router as auth_router
from .tryon.router import router as tryon_router

router = APIRouter()
router.include_router(tryon_router)
router.include_router(auth_router)

__all__ = ["router", "auth_router", "tryon_router"]
