import base64
import json
from typing import List, Dict, Any

import httpx
from genkit.ai import Genkit
from genkit.plugins.google_genai import GoogleAI

# Import from centralized config
from src.config import GEMINI_KEY, logger
from src.core.prompt_templates import build_virtual_tryon_prompt, build_audit_prompt

# Initialize Genkit with API key from config
GEMINI_API_KEY = GEMINI_KEY
ai = Genkit(plugins=[GoogleAI(api_key=GEMINI_API_KEY)])

logger.info(f"Gemini module initialized with API key: {bool(GEMINI_API_KEY)}")


async def virtual_tryon(
    body_url: str,
    garment_urls: List[str],
) -> Dict[str, str]:
    """
    Generate a virtual try-on image using Gemini AI.

    Args:
        body_url: Appwrite file URL of the body/user image
        garment_urls: List of 1-2 Appwrite file URLs for garment images

    Returns:
        Dict with format: {"result_base64": "<base64_string>"}

    Raises:
        ValueError: If garment_urls is empty or has more than 2 items
        Exception: If API call fails or URL fetching fails
    """
    # Validate inputs
    if not garment_urls or len(garment_urls) > 2:
        raise ValueError("Must provide 1 or 2 garment URLs")

    # Fetch and convert all images to base64
    body_b64 = await _prepare_image_input(body_url, "body image")

    logger.info(f"Preparing {len(garment_urls)} garment image(s)")
    garments_b64 = []
    for idx, garment_ref in enumerate(garment_urls):
        garments_b64.append(
            await _prepare_image_input(garment_ref, f"garment image {idx + 1}")
        )

    # Build the prompt based on number of garments using modular template
    num_garments = len(garment_urls)
    prompt = build_virtual_tryon_prompt(num_garments)

    # Log the prompt
    logger.info("=" * 80)
    logger.info("VIRTUAL TRY-ON PROMPT:")
    logger.info(prompt)
    logger.info("=" * 80)

    # Prepare the content parts for Gemini API
    # Order: garment images first, then body image, then text prompt
    content_parts = []

    # Add garment images
    for garment_b64 in garments_b64:
        content_parts.append(
            {"inline_data": {"mime_type": "image/jpeg", "data": garment_b64}}
        )

    # Add body image
    content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": body_b64}})

    # Add text prompt
    content_parts.append({"text": prompt})

    # Call Gemini API directly using httpx
    # Note: Direct API call since Genkit's multimodal Part class support is limited
    try:
        gemini_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash-image-preview:generateContent?key={GEMINI_API_KEY}"
        )

        # Build payload
        gemini_payload = {
            "contents": [{"parts": content_parts}],
            "generationConfig": {
                "temperature": 0.4,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 4096,
            },
        }

        # Make async request
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                gemini_url,
                json=gemini_payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            api_result = response.json()

        # Extract base64 image from response
        if "candidates" not in api_result or not api_result["candidates"]:
            raise Exception("Gemini API returned no candidates")

        candidate = api_result["candidates"][0]
        if "content" not in candidate or "parts" not in candidate["content"]:
            raise Exception("Invalid Gemini API response structure")

        # Find the image in the response parts
        result_base64 = None
        for part in candidate["content"]["parts"]:
            # Check both camelCase and snake_case formats
            if "inlineData" in part and "data" in part["inlineData"]:
                result_base64 = part["inlineData"]["data"]
                break
            elif "inline_data" in part and "data" in part["inline_data"]:
                result_base64 = part["inline_data"]["data"]
                break

        if not result_base64:
            raise Exception("No image found in Gemini API response")

        return {"result_base64": result_base64}

    except httpx.HTTPStatusError as e:
        raise Exception(
            f"Gemini API HTTP error: {e.response.status_code} - {e.response.text}"
        )
    except httpx.RequestError as e:
        raise Exception(f"Network error calling Gemini API: {str(e)}")
    except Exception as e:
        raise Exception(f"Virtual try-on generation failed: {str(e)}")


# Export for use in routers
async def _prepare_image_input(reference: str, label: str) -> str:
    """Normalize an image reference (URL, data URI, or base64 string) to raw base64."""

    try:
        if _is_url(reference):
            logger.info(f"Fetching {label} from URL: {reference}")
        elif reference.startswith("data:"):
            logger.info(f"Using data URI provided for {label}")
        else:
            logger.info(f"Using base64 payload provided for {label}")

        return await _fetch_and_encode(reference)
    except Exception as exc:
        logger.error(f"Failed to prepare {label}: {exc}")
        raise


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


async def _fetch_and_encode(reference: str, timeout: float = 60.0) -> str:
    """Return a base64-encoded representation of the supplied image reference."""

    if _is_url(reference):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(reference)
                response.raise_for_status()
                return base64.b64encode(response.content).decode("utf-8")
        except httpx.HTTPStatusError as exc:
            raise Exception(
                f"Failed to fetch image from {reference}: HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise Exception(f"Network error fetching {reference}: {exc}") from exc

    if reference.startswith("data:"):
        try:
            return reference.split(",", 1)[1]
        except IndexError as exc:
            raise Exception("Invalid data URI provided for image input") from exc

    cleaned = reference.strip()
    if not cleaned:
        raise Exception("Empty base64 image input provided")

    # Basic validation: ensure length compatible with base64
    try:
        base64.b64decode(cleaned, validate=True)
    except Exception as exc:
        raise Exception("Provided image string is not valid base64") from exc

    return cleaned


async def audit_tryon_result(
    model_before: str,
    model_after: str,
    garment1: str,
    garment2: str | None = None,
) -> Dict[str, Any]:
    """Evaluate a generated try-on result using Gemini multimodal capabilities."""

    if not model_before or not model_after or not garment1:
        raise ValueError(
            "model_before, model_after, and garment1 are required inputs for auditing"
        )

    prompt = build_audit_prompt()

    logger.info("Preparing inputs for try-on audit")
    before_b64 = await _prepare_image_input(model_before, "model_before image")
    after_b64 = await _prepare_image_input(model_after, "model_after image")
    garment1_b64 = await _prepare_image_input(garment1, "garment1 image")
    garment2_b64 = None
    if garment2:
        garment2_b64 = await _prepare_image_input(garment2, "garment2 image")

    parts = [
        {"text": prompt},
        {"text": "model_before"},
        {"inline_data": {"mime_type": "image/jpeg", "data": before_b64}},
        {"text": "model_after"},
        {"inline_data": {"mime_type": "image/jpeg", "data": after_b64}},
        {"text": "garment1"},
        {"inline_data": {"mime_type": "image/jpeg", "data": garment1_b64}},
    ]

    if garment2_b64:
        parts.extend(
            [
                {"text": "garment2"},
                {"inline_data": {"mime_type": "image/jpeg", "data": garment2_b64}},
            ]
        )

    audit_url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent"
    )

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "topK": 32,
            "topP": 0.9,
            "maxOutputTokens": 1024,
        },
    }

    try:
        headers = {"Content-Type": "application/json"}
        if GEMINI_API_KEY:
            headers["x-goog-api-key"] = GEMINI_API_KEY

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                audit_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            api_result = response.json()

        if "candidates" not in api_result or not api_result["candidates"]:
            raise Exception("Gemini audit returned no candidates")

        candidate = api_result["candidates"][0]
        if "content" not in candidate or "parts" not in candidate["content"]:
            raise Exception("Invalid Gemini audit response structure")

        result_text = ""
        for part in candidate["content"]["parts"]:
            if "text" in part:
                result_text += part["text"]

        if not result_text:
            raise Exception("Audit response contained no text output")

        logger.info(f"Audit raw response text: {result_text[:500]}...")
        parsed = _extract_json(result_text)
        return parsed

    except httpx.HTTPStatusError as exc:
        raise Exception(
            f"Gemini audit HTTP error: {exc.response.status_code} - {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise Exception(f"Network error calling Gemini audit: {exc}") from exc
    except Exception as exc:
        logger.error(f"Audit failed with error: {exc}")
        # Log the full API response for debugging
        if "api_result" in locals():
            logger.error(
                f"Full API response: {json.dumps(api_result, indent=2)[:1000]}"
            )
        raise


def _extract_json(raw_text: str) -> Dict[str, Any]:
    """Attempt to parse a JSON object from the model's text output."""

    cleaned = raw_text.strip()

    # Remove markdown code block delimiters
    if cleaned.startswith("```"):
        # Find the first newline after ``` to skip the language identifier
        first_newline = cleaned.find("\n")
        if first_newline > 0:
            cleaned = cleaned[first_newline + 1 :]
        # Remove trailing ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            f"Failed to parse JSON from audit response. Raw text: {raw_text[:500]}"
        )
        logger.error(f"Cleaned text: {cleaned[:500]}")
        raise Exception(f"Audit response was not valid JSON: {str(exc)}") from exc

    expected_keys = {
        "clothing_changed",
        "matches_input_garments",
        "visual_quality_score",
        "issues",
        "summary",
    }

    missing_keys = expected_keys - set(data.keys())
    if missing_keys:
        logger.error(f"Audit JSON missing keys: {missing_keys}")
        logger.error(f"Received keys: {list(data.keys())}")
        logger.error(f"Full response data: {json.dumps(data, indent=2)[:500]}")
        raise Exception(f"Audit JSON is missing required keys: {missing_keys}")

    return data


__all__ = ["virtual_tryon", "audit_tryon_result", "ai"]
