import asyncio
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
            "Create a professional e-commerce fashion photo. "
            "Take the clothing item from the first image and let the person from the second image wear it. "
            "Generate a realistic, full-body shot of the person wearing the clothing, "
            "with the lighting and shadows adjusted to match the environment. "
            "Output only the final image, no text or explanations."
        )
    else:
        prompt = (
            f"Create a professional e-commerce fashion photo. "
            f"Take the {num_garments} clothing items from the first {num_garments} images "
            f"and let the person from the last image wear them together. "
            f"Generate a realistic, full-body shot of the person wearing all the clothing items, "
            f"with the lighting and shadows adjusted to match the environment. "
            f"Output only the final image, no text or explanations."
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


async def test_virtual_tryon():
    """Test the virtual_tryon function with sample Appwrite URLs"""
    print("\n" + "=" * 70)
    print("👕 TESTING VIRTUAL TRY-ON FUNCTION (URL-based)")
    print("=" * 70 + "\n")

    # Example test with public image URLs
    # Replace these with actual Appwrite URLs for real testing

    # Using placeholder public URLs (these are sample images)
    sample_body_url = (
        "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400"
    )
    sample_garment_url = (
        "https://images.unsplash.com/photo-1581655353564-df123a1eb820?w=400"
    )

    print("⚠️  NOTE: Update test URLs to your Appwrite URLs for real testing")
    print(f"Body URL: {sample_body_url[:60]}...")
    print(f"Garment URL: {sample_garment_url[:60]}...")

    print("\n" + "-" * 70)
    print("Testing with 1 garment (using public URLs):")
    print("-" * 70)
    try:
        result = await virtual_tryon(
            body_url=sample_body_url, garment_urls=[sample_garment_url]
        )
        print(
            f"✅ Success! Got base64 result (length: {len(result['result_base64'])} chars)"
        )
        print(f"   First 100 chars: {result['result_base64'][:100]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "=" * 70)
    print("📝 USAGE EXAMPLE:")
    print("=" * 70)
    print("""
# In your router/API:
from src.core.gemini import virtual_tryon
from src.core.upload_to_appwrite import upload_to_appwrite

@router.post("/tryon")
async def tryon_endpoint(
    body_image: UploadFile = File(...),
    garment1: UploadFile = File(...),
    garment2: Optional[UploadFile] = File(None)
):
    # Upload files to Appwrite and get URLs
    body_url = await upload_to_appwrite(body_image)
    garment1_url = await upload_to_appwrite(garment1)
    
    garment_urls = [garment1_url]
    if garment2:
        garment2_url = await upload_to_appwrite(garment2)
        garment_urls.append(garment2_url)
    
    # Generate try-on using URLs
    result = await virtual_tryon(body_url=body_url, garment_urls=garment_urls)
    
    # Return JSON: {"result_base64": "..."}
    return result
    """)
    print("=" * 70 + "\n")


if __name__ == "__main__":
    print("🚀 Testing Genkit AI with Gemini...\n")

    # Test basic generation
    # asyncio.run(test())

    # Test short prompt
    # asyncio.run(test_short())

    # Test virtual try-on function
    asyncio.run(test_virtual_tryon())
