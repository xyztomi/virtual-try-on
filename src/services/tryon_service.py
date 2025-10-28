"""Services for asynchronous try-on processing and auditing."""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

import httpx

from src.config import GEMINI_KEY, logger
from src.core import database_ops, storage_ops
from src.core.gemini import virtual_tryon, _prepare_image_input  # noqa: F401
from src.core.prompt_templates import build_audit_prompt

MIN_AUDIT_SCORE = 60.0
AUDIT_TIMEOUT_SECONDS = 120.0


def _log(level: int, message: str, **context: Any) -> None:
    """Helper to emit structured logs with contextual metadata."""
    logger.log(level, "%s | context=%s", message, context)


@dataclass(slots=True)
class AuditResultData:
    """Lightweight container for audit evaluation results."""

    clothing_changed: bool
    matches_input_garments: bool
    visual_quality_score: float
    issues: List[str]
    summary: str

    def quality_passed(self, min_score: float = MIN_AUDIT_SCORE) -> bool:
        """Return True when audit meets the acceptance criteria."""
        return (
            self.clothing_changed
            and self.matches_input_garments
            and self.visual_quality_score >= min_score
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clothing_changed": self.clothing_changed,
            "matches_input_garments": self.matches_input_garments,
            "visual_quality_score": float(self.visual_quality_score),
            "issues": self.issues,
            "summary": self.summary,
        }


@dataclass(slots=True)
class TryOnJobContext:
    """Metadata passed to the background try-on worker."""

    record_id: str
    body_url: str
    garment_urls: List[str]
    user_history_record_id: Optional[str]
    client_ip: Optional[str]
    max_retries: int = 2


async def process_tryon_job(context: TryOnJobContext) -> None:
    """Background worker that generates and audits a try-on result."""

    start_time = time.time()
    _log(
        logging.INFO,
        "tryon_job_started",
        record_id=context.record_id,
        retries=context.max_retries,
    )

    result_url: Optional[str] = None
    audit_result: Optional[AuditResultData] = None

    for attempt in range(context.max_retries):
        attempt_idx = attempt + 1
        _log(
            logging.INFO,
            "generation_attempt_started",
            record_id=context.record_id,
            attempt=attempt_idx,
        )

        generation_payload = await _run_generation(context, attempt_idx)
        if generation_payload is None:
            if attempt_idx >= context.max_retries:
                await _mark_failure(
                    context,
                    reason="AI generation failed",
                    retry_count=attempt,
                )
            continue

        result_base64 = generation_payload["result_base64"]

        upload_payload = await _upload_result_image(
            context.record_id,
            result_base64,
            attempt_idx,
        )
        if upload_payload is None:
            if attempt_idx >= context.max_retries:
                await _mark_failure(
                    context,
                    reason="Failed to upload generated result",
                    retry_count=attempt,
                )
            continue

        result_url = upload_payload

        audit_result = await _run_audit(context, result_url)
        if audit_result and audit_result.quality_passed():
            break

        _log(
            logging.WARNING,
            "audit_failed",
            record_id=context.record_id,
            attempt=attempt_idx,
            audit=audit_result.to_dict() if audit_result else None,
        )

        if attempt_idx >= context.max_retries:
            _log(
                logging.INFO,
                "using_last_attempt_result",
                record_id=context.record_id,
                attempt=attempt_idx,
            )
            break

        await _cleanup_result_url(result_url)
        result_url = None

    if not result_url:
        await _mark_failure(
            context,
            reason="No acceptable try-on result after retries",
            retry_count=context.max_retries,
        )
        return

    processing_time_ms = int((time.time() - start_time) * 1000)
    await _mark_success(
        context,
        result_url=result_url,
        audit_result=audit_result,
        retry_count=(attempt_idx - 1),
        processing_time_ms=processing_time_ms,
    )


async def _run_generation(
    context: TryOnJobContext, attempt: int
) -> Optional[Dict[str, str]]:
    try:
        payload = await virtual_tryon(
            body_url=context.body_url,
            garment_urls=context.garment_urls,
        )
        _log(
            logging.INFO,
            "generation_complete",
            record_id=context.record_id,
            attempt=attempt,
        )
        return payload
    except Exception as exc:
        _log(
            logging.ERROR,
            "generation_error",
            record_id=context.record_id,
            attempt=attempt,
            error=str(exc),
        )
        return None


async def _upload_result_image(
    record_id: str,
    result_base64: str,
    attempt: int,
) -> Optional[str]:
    try:
        result_bytes = base64.b64decode(result_base64)
        result_url = await storage_ops.upload_result_image(
            file_bytes=result_bytes,
            filename=f"result_{record_id}_attempt{attempt}.jpg",
            content_type="image/jpeg",
        )
        _log(
            logging.INFO,
            "result_uploaded",
            record_id=record_id,
            attempt=attempt,
            result_url=result_url,
        )
        return result_url
    except Exception as exc:
        _log(
            logging.ERROR,
            "result_upload_error",
            record_id=record_id,
            attempt=attempt,
            error=str(exc),
        )
        return None


async def _run_audit(
    context: TryOnJobContext,
    result_url: str,
) -> Optional[AuditResultData]:
    try:
        garment2 = context.garment_urls[1] if len(context.garment_urls) > 1 else None
        audit = await audit_tryon_result(
            model_before=context.body_url,
            model_after=result_url,
            garment1=context.garment_urls[0],
            garment2=garment2,
        )
        if audit:
            _log(
                logging.INFO,
                "audit_complete",
                record_id=context.record_id,
                audit=audit.to_dict(),
            )
        else:
            _log(
                logging.WARNING,
                "audit_no_data",
                record_id=context.record_id,
            )
        return audit
    except Exception as exc:
        _log(
            logging.ERROR,
            "audit_error",
            record_id=context.record_id,
            error=str(exc),
        )
        return None


async def audit_tryon_result(
    model_before: str,
    model_after: str,
    garment1: str,
    garment2: Optional[str] = None,
) -> Optional[AuditResultData]:
    parts = []
    prompt = build_audit_prompt()
    parts.append({"text": prompt})

    before_b64 = await _prepare_image_input(model_before, "model_before image")
    parts.extend(
        [
            {"text": "model_before"},
            {"inline_data": {"mime_type": "image/jpeg", "data": before_b64}},
        ]
    )

    after_b64 = await _prepare_image_input(model_after, "model_after image")
    parts.extend(
        [
            {"text": "model_after"},
            {"inline_data": {"mime_type": "image/jpeg", "data": after_b64}},
        ]
    )

    garment1_b64 = await _prepare_image_input(garment1, "garment1 image")
    parts.extend(
        [
            {"text": "garment1"},
            {"inline_data": {"mime_type": "image/jpeg", "data": garment1_b64}},
        ]
    )

    if garment2:
        garment2_b64 = await _prepare_image_input(garment2, "garment2 image")
        parts.extend(
            [
                {"text": "garment2"},
                {"inline_data": {"mime_type": "image/jpeg", "data": garment2_b64}},
            ]
        )

    payload_data = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "topK": 32,
            "topP": 0.9,
            "maxOutputTokens": 3048,
        },
    }

    headers = {"Content-Type": "application/json"}
    if GEMINI_KEY:
        headers["x-goog-api-key"] = GEMINI_KEY

    async with httpx.AsyncClient(timeout=AUDIT_TIMEOUT_SECONDS) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            json=payload_data,
            headers=headers,
        )
        response.raise_for_status()
        api_result = response.json()

    if "error" in api_result:
        _log(logging.ERROR, "audit_api_error", error=api_result["error"])
        return None

    if "candidates" not in api_result or not api_result["candidates"]:
        _log(logging.ERROR, "audit_no_candidates", response=api_result)
        return None

    candidate = api_result["candidates"][0]
    if candidate.get("finishReason") and candidate["finishReason"] != "STOP":
        _log(
            logging.WARNING,
            "audit_finish_reason",
            finish_reason=candidate["finishReason"],
        )
        return None

    parts = candidate.get("content", {}).get("parts", [])
    text_output = "".join(part.get("text", "") for part in parts if "text" in part)

    if not text_output:
        _log(logging.ERROR, "audit_empty_text")
        return None

    cleaned = text_output.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline > 0:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    audit_payload = json.loads(cleaned)

    missing_keys = {
        "clothing_changed",
        "matches_input_garments",
        "visual_quality_score",
        "issues",
        "summary",
    } - set(audit_payload.keys())

    if missing_keys:
        _log(logging.ERROR, "audit_missing_keys", missing=list(missing_keys))
        return None

    return AuditResultData(
        clothing_changed=bool(audit_payload["clothing_changed"]),
        matches_input_garments=bool(audit_payload["matches_input_garments"]),
        visual_quality_score=float(audit_payload["visual_quality_score"]),
        issues=list(audit_payload.get("issues", [])),
        summary=str(audit_payload["summary"]),
    )


async def _cleanup_result_url(result_url: str) -> None:
    path = result_url.split("/images/")[-1]
    try:
        await storage_ops.delete_file(path)
        _log(logging.DEBUG, "intermediate_result_deleted", path=path)
    except Exception as exc:
        _log(logging.WARNING, "cleanup_failed", path=path, error=str(exc))


async def _mark_success(
    context: TryOnJobContext,
    result_url: str,
    audit_result: Optional[AuditResultData],
    retry_count: int,
    processing_time_ms: int,
) -> None:
    audit_dict = audit_result.to_dict() if audit_result else None

    try:
        await database_ops.update_tryon_result(
            record_id=context.record_id,
            result_url=result_url,
            processing_time_ms=processing_time_ms,
            audit_score=(audit_result.visual_quality_score if audit_result else None),
            audit_details=audit_dict,
            retry_count=retry_count,
        )
    except Exception as exc:
        _log(
            logging.WARNING,
            "result_update_failed",
            record_id=context.record_id,
            error=str(exc),
        )

    _log(
        logging.INFO,
        "tryon_job_completed",
        record_id=context.record_id,
        result_url=result_url,
        retry_count=retry_count,
        audit=audit_dict,
        processing_time_ms=processing_time_ms,
    )


async def _mark_failure(
    context: TryOnJobContext,
    reason: str,
    retry_count: int,
) -> None:
    try:
        await database_ops.mark_tryon_failed(
            context.record_id,
            reason,
            retry_count=retry_count,
        )
    except Exception as exc:
        _log(
            logging.ERROR,
            "result_mark_failed_error",
            record_id=context.record_id,
            error=str(exc),
        )

    _log(
        logging.WARNING,
        "tryon_job_failed",
        record_id=context.record_id,
        reason=reason,
        retry_count=retry_count,
    )
