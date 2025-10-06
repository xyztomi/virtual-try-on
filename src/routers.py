from fastapi import APIRouter

from .models import TryonRequest

router = APIRouter()


@router.post("/tryon")
def submit(req: TryonRequest):
    pass
