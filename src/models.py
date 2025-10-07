from pydantic import BaseModel, HttpUrl
from typing import List


class TryonRequest(BaseModel):
    cf_token: str
    body_url: HttpUrl
    garment_urls: List[HttpUrl]


class OnAcceptedTryonResponse(BaseModel):
    session_id: str
    status: str


class OnSuccessTryonResponse(BaseModel):
    session_id: str
    status: str
    result_url: HttpUrl


class OnErrorTryonResponse(BaseModel):
    error: str
