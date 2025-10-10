import base64
from typing import List, Dict

import httpx
from genkit.ai import Genkit
from genkit.plugins.google_genai import GoogleAI

# Import from centralized config
from src.config import GEMINI_KEY, logger

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

    # Helper to fetch image from URL and convert to base64
    async def fetch_and_encode(url: str) -> str:
        """Fetch image from URL and encode to base64"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                image_bytes = response.content
                return base64.b64encode(image_bytes).decode("utf-8")
        except httpx.HTTPStatusError as e:
            raise Exception(
                f"Failed to fetch image from {url}: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            raise Exception(f"Network error fetching {url}: {str(e)}")

    # Fetch and convert all images to base64
    logger.info(f"Fetching body image from: {body_url}")
    body_b64 = await fetch_and_encode(body_url)

    logger.info(f"Fetching {len(garment_urls)} garment image(s)")
    garments_b64 = []
    for idx, garment_url in enumerate(garment_urls):
        logger.info(f"Fetching garment {idx + 1} from: {garment_url}")
        garment_b64 = await fetch_and_encode(garment_url)
        garments_b64.append(garment_b64)

        # Build the prompt based on number of garments
    num_garments = len(garment_urls)
    if num_garments == 1:
        prompt = (
            "You are an expert virtual try-on system. Your task is to create a photorealistic try-on image.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "1. PRESERVE THE ORIGINAL: Keep the person's face, body shape, pose, and entire background EXACTLY as shown in the body image. Do not modify anything except the garment area.\n\n"
            "2. AUTOMATIC GARMENT DETECTION: Analyze the garment image to automatically identify what type of clothing it is (e.g., hoodie, hat, pants, shirt, jacket, shoes, accessories).\n\n"
            "3. INTELLIGENT PLACEMENT: Based on the detected garment type, place it in the appropriate position on the body:\n"
            "   - Hats/caps → top of head\n"
            "   - Hoodies/shirts/jackets → upper body/torso\n"
            "   - Pants/jeans/shorts → lower body/legs\n"
            "   - Shoes/sneakers → feet\n"
            "   - Accessories → appropriate location\n\n"
            "4. NATURAL INTEGRATION: Replace or overlay ONLY the specific clothing area that matches the garment type. The garment must:\n"
            "   - Fit naturally to the person's body shape and contours\n"
            "   - Match the lighting, shadows, and perspective of the original body image\n"
            "   - Blend seamlessly with visible skin and unchanged clothing\n"
            "   - Maintain realistic fabric physics (wrinkles, folds, texture)\n\n"
            "5. FALLBACK RULE: If you cannot confidently determine what type of garment this is or where it should be placed, return the original body image unchanged.\n\n"
            "6. OUTPUT: Generate only the final photorealistic image with no text, labels, or explanations.\n\n"
            "Now, analyze the garment in the first image and apply it to the person in the second image following all rules above."
        )
    else:
        prompt = (
            f"You are an expert virtual try-on system. Your task is to create a photorealistic try-on image with {num_garments} garments.\n\n"
            f"CRITICAL REQUIREMENTS:\n"
            f"1. PRESERVE THE ORIGINAL: Keep the person's face, body shape, pose, and entire background EXACTLY as shown in the body image. Do not modify anything except the garment areas.\n\n"
            f"2. AUTOMATIC GARMENT DETECTION: Analyze each of the {num_garments} garment images to automatically identify what type of clothing they are (e.g., hoodie, hat, pants, shirt, jacket, shoes, accessories).\n\n"
            f"3. INTELLIGENT PLACEMENT: Based on the detected garment types, place each item in the appropriate position on the body:\n"
            f"   - Hats/caps → top of head\n"
            f"   - Hoodies/shirts/jackets → upper body/torso\n"
            f"   - Pants/jeans/shorts → lower body/legs\n"
            f"   - Shoes/sneakers → feet\n"
            f"   - Accessories → appropriate location\n\n"
            f"4. NATURAL INTEGRATION: Replace or overlay ONLY the specific clothing areas that match each garment type. Each garment must:\n"
            f"   - Fit naturally to the person's body shape and contours\n"
            f"   - Match the lighting, shadows, and perspective of the original body image\n"
            f"   - Blend seamlessly with visible skin and other unchanged clothing\n"
            f"   - Maintain realistic fabric physics (wrinkles, folds, texture)\n"
            f"   - Work harmoniously with the other garments\n\n"
            f"5. FALLBACK RULE: If you cannot confidently determine what type any garment is or where it should be placed, return the original body image unchanged.\n\n"
            f"6. OUTPUT: Generate only the final photorealistic image with no text, labels, or explanations.\n\n"
            f"Now, analyze the garments in the first {num_garments} images and apply them to the person in the last image following all rules above."
        )

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
__all__ = ["virtual_tryon", "ai"]
