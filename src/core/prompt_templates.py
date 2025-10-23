"""Prompt templates and builders for Optimind’s Gemini virtual try-on flows."""

from __future__ import annotations
from dataclasses import dataclass


# --- GENERATION PROMPT ---

PROMPT_TEMPLATE = """Generate ONE high-quality photorealistic image of the Person Image model now wearing garments from the provided garment photos.

Guidelines:
- Apply Garment Image 1 naturally onto the model’s body, REPLACING any existing clothing of the same type. If Garment Image 2 is provided, show BOTH garments: layer it only when naturally worn on top, otherwise replace the relevant clothing. {GARMENT_1_DESCRIPTION}. {GARMENT_2_AND_LAYOUT_DESCRIPTION}
- When the Person Image is cropped (e.g., only upper body visible), infer unseen areas and ensure each garment is fully visible within the frame.
- Completely remove remnants of original clothing that should no longer appear.
- Keep the model’s identity, pose, facial features, body shape, skin tone, and hair identical to the Person Image.
- Preserve the background, keeping it clean and natural; remove any garment artifacts or mismatched lighting.
- Match lighting, color tone, and texture realism to the Person Image. Use {STYLE_AESTHETIC} aesthetics with {LIGHTING_DESCRIPTION}.
- Maintain original camera framing, perspective, and realism as if shot with a {CAMERA_LENS_TYPE} producing {CAMERA_EFFECTS}.
- Avoid distortions, extra limbs, or text/graphics.

Return only the final photorealistic image output.
"""


@dataclass(frozen=True)
class PromptDefaults:
    """Default configuration values for virtual try-on generation prompts."""

    garment_single: str = (
        "Use the first garment image to identify the clothing type, fabric, and color. "
        "Replace the corresponding item on the model so it matches naturally and remains fully visible."
    )
    garment_duo: str = (
        "Additionally, integrate the second garment shown. Ensure both garments are correctly layered or replaced "
        "based on clothing type (e.g., jacket over shirt). Each garment must remain clearly visible without overlap artefacts."
    )
    style_aesthetic: str = (
        "a clean, realistic photographic style matching the original photo"
    )
    lighting_description: str = "natural lighting with realistic shadows and fabric textures that blend with the original scene"
    lighting_description_duo: str = "consistent natural lighting for all garments, maintaining accurate texture, folds, and shadows"
    camera_lens_type: str = "a realistic focal length consistent with the Person Image"
    camera_effects: str = (
        "sharp focus, natural depth of field, and lifelike texture rendering"
    )


DEFAULTS = PromptDefaults()


def build_virtual_tryon_prompt(
    garment_count: int,
    garment_1_description: str | None = None,
    garment_2_and_layout_description: str | None = None,
    style_aesthetic: str | None = None,
    lighting_description: str | None = None,
    camera_lens_type: str | None = None,
    camera_effects: str | None = None,
) -> str:
    """Render the Nano Banana generation prompt with provided configuration."""
    if garment_count not in {1, 2}:
        raise ValueError("Virtual try-on prompt supports only 1 or 2 garment images.")

    garment_1 = garment_1_description or DEFAULTS.garment_single
    garment_2 = garment_2_and_layout_description or (
        DEFAULTS.garment_duo if garment_count == 2 else ""
    )

    style = style_aesthetic or DEFAULTS.style_aesthetic
    lighting = lighting_description or (
        DEFAULTS.lighting_description_duo
        if garment_count == 2
        else DEFAULTS.lighting_description
    )
    camera_type = camera_lens_type or DEFAULTS.camera_lens_type
    camera_fx = camera_effects or DEFAULTS.camera_effects

    return PROMPT_TEMPLATE.format(
        GARMENT_1_DESCRIPTION=garment_1,
        GARMENT_2_AND_LAYOUT_DESCRIPTION=garment_2,
        STYLE_AESTHETIC=style,
        LIGHTING_DESCRIPTION=lighting,
        CAMERA_LENS_TYPE=camera_type,
        CAMERA_EFFECTS=camera_fx,
    )


# --- AUDIT PROMPT ---

AUDIT_PROMPT_TEMPLATE = """Anda adalah AI auditor visual untuk sistem virtual try-on Optimind.

Tujuan:
Bandingkan model asli (model_before) dan hasil try-on yang dihasilkan (model_after) dengan gambar referensi pakaian yang diberikan untuk memverifikasi apakah pakaian diganti dengan akurat dan realistis.

Input (sudah disediakan sebagai gambar inline):
- model_before
- model_after
- garment1
- garment2 (opsional)

Tugas:
1. Deskripsikan pakaian yang terlihat di gambar sebelum dan sesudah.
2. Tentukan apakah garment1 (dan garment2, jika ada) diterapkan dengan benar di gambar sesudah.
3. Evaluasi kualitas blending, konsistensi pencahayaan, dan artefak visual apa pun.
4. Kembalikan JSON saja dalam skema berikut:

{
  "clothing_changed": true/false,
  "matches_input_garments": true/false,
  "visual_quality_score": angka (0-100),
  "issues": ["artefak", "pencahayaan buruk", "ketidaksesuaian pose"],
  "summary": "satu kalimat ringkasan singkat dalam bahasa Indonesia"
}

Aturan:
- "clothing_changed" = true hanya jika outfit jelas berbeda dari model_before.
- "matches_input_garments" = true hanya jika pakaian yang diterapkan sesuai dengan referensi yang diberikan.
- Jika clothing_changed false atau kualitas buruk, set "visual_quality_score" di bawah 60.
- Selalu sertakan label issue yang relevan; gunakan [] jika tidak ada.
- Respons hanya berupa raw JSON (tanpa markdown, komentar, atau teks di luar objek).
- Bersikaplah objektif dan ringkas; summary harus satu kalimat dalam bahasa Indonesia.
- Gunakan bahasa Indonesia untuk semua penjelasan dalam field "issues" dan "summary".
"""


def build_audit_prompt() -> str:
    """Return the fixed audit prompt template."""
    return AUDIT_PROMPT_TEMPLATE


__all__ = [
    "PROMPT_TEMPLATE",
    "AUDIT_PROMPT_TEMPLATE",
    "DEFAULTS",
    "PromptDefaults",
    "build_virtual_tryon_prompt",
    "build_audit_prompt",
]
