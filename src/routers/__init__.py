"""Router package exposing all API routers."""

from fastapi import APIRouter

from .tryon.router import router as tryon_router

router = APIRouter()
router.include_router(tryon_router)

__all__ = ["router"]
