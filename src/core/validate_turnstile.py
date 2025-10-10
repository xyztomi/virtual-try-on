from typing import Optional
import os

import pydantic
import requests


cloudflare_secret_key = os.getenv("TURNSTILE_SECRET")


# Export the main validation function
__all__ = ["validate_turnstile", "SiteVerifyResponse", "init"]


class SiteVerifyRequest(pydantic.BaseModel):
    secret: str
    response: str
    remoteip: Optional[str] = None


class SiteVerifyResponse(pydantic.BaseModel):
    success: bool
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    error_codes: list[str] = pydantic.Field(alias="error-codes", default_factory=list)
    action: Optional[str] = None
    cdata: Optional[str] = None


request_example = {
    "secret": "0x5ABAAFAAAn72SdCAP75q6sPP9P6zooFZt",
    "response": "???",
    "remoteip": "1.2.3.4",
}

success_example = {
    "success": True,
    "challenge_ts": "2022-02-28T15:14:30.096Z",
    "hostname": "example.com",
    "error-codes": [],
    "action": "login",
    "cdata": "session_id-123456789",
}

failure_example = {
    "success": False,
    "hostname": "",
    "error-codes": ["invalid-input-response"],
}


def validate_turnstile(
    turnstile_response: str, user_ip: Optional[str] = None
) -> SiteVerifyResponse:
    """Validate a Turnstile captcha token.

    Args:
        turnstile_response: The Turnstile response token from the client
        user_ip: Optional IP address of the user

    Returns:
        SiteVerifyResponse with validation result
    """
    if not cloudflare_secret_key:
        raise Exception("TURNSTILE_SECRET environment variable must be set.")

    if not turnstile_response:
        model = SiteVerifyResponse(success=False, hostname=None)
        model.error_codes.append("Submitted with no cloudflare client response")
        return model

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    model = SiteVerifyRequest(
        secret=cloudflare_secret_key, response=turnstile_response, remoteip=user_ip
    )
    try:
        resp = requests.post(url, data=model.dict())
        if resp.status_code != 200:
            model = SiteVerifyResponse(success=False, hostname=None)
            model.error_codes.extend(
                [
                    f"Failure status code: {resp.status_code}",
                    f"Failure details: {resp.text}",
                ]
            )
            return model

        site_response = SiteVerifyResponse(**resp.json())
        return site_response
    except Exception as x:
        model = SiteVerifyResponse(success=False, hostname=None)
        model.error_codes.extend(
            ["Failure status code: Unknown", f"Failure details: {x}"]
        )
        return model


def init(secret_key: str):
    global cloudflare_secret_key

    if not secret_key:
        return

    cloudflare_secret_key = secret_key.strip()
