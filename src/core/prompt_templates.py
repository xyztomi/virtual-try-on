"""Prompt templates and builders for Gemini virtual try-on flows."""

from __future__ import annotations

from dataclasses import dataclass


PROMPT_TEMPLATE = """Generate ONE photorealistic image of the Person Image model now wearing garments taken from the provided garment product photos. Guidance:

- Apply the garment from Garment Image 1 so it fits naturally on the model's body and REPLACE any conflicting clothing of the same category from the Person Image. If a second garment image is supplied, only layer it when it is naturally worn on top; otherwise it should also replace the original clothing: {GARMENT_1_DESCRIPTION}. {GARMENT_2_AND_LAYOUT_DESCRIPTION}
- Remove or hide any part of the original outfit that should no longer be visible, ensuring no remnants of the previous garment remain.
- Keep the model's facial features, identity, pose, body shape, skin tone, and hair exactly the same as in the Person Image.
- Preserve the original background and keep it clean, simple, and neutral—remove any garment artefacts that do not belong in the scene.
- Match lighting, shadows, and overall style to the Person Image. Use {STYLE_AESTHETIC} styling with {LIGHTING_DESCRIPTION}.
- Maintain the original framing, camera perspective, and natural photographic quality, as if shot with a {CAMERA_LENS_TYPE} producing {CAMERA_EFFECTS}.
- Avoid any distortions, extra limbs, or visual artefacts. Do not add text or graphics.

Return only the final photorealistic image.
"""


@dataclass(frozen=True)
class PromptDefaults:
    """Default configuration values for the virtual try-on prompt."""

    garment_single: str = (
        "the garment shown in the first image. Analyze its type, fabric texture, color, "
        "and design features, then replace the corresponding clothing on the model with it"
    )
    garment_duo: str = (
        "Additionally, the model is wearing the secondary garment shown in the second image. "
        "Ensure both garments are positioned correctly based on their detected types. When appropriate, "
        "layer the second garment naturally (e.g., jacket over shirt); otherwise replace the original "
        "clothing item so only the intended garments remain visible"
    )
    style_aesthetic: str = (
        "a natural, photorealistic style that matches the original photograph"
    )
    lighting_description: str = (
        "natural lighting with realistic shadows and highlights that match the original scene. "
        "Ensure fabric folds, wrinkles, and texture are properly lit"
    )
    lighting_description_duo: str = (
        "natural lighting with realistic shadows and highlights that match the original scene. "
        "Ensure all garments have consistent lighting with proper fabric folds, wrinkles, and texture"
    )
    camera_lens_type: str = "natural focal length that matches the original photograph"
    camera_effects: str = "sharp focus with natural depth of field"


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
    """Render the NANO BANANA prompt with the provided configuration."""
    if garment_count not in {1, 2}:
        raise ValueError("Virtual try-on prompt supports 1 or 2 garment images")

    garment_1 = garment_1_description or DEFAULTS.garment_single
    garment_2 = ""
    if garment_count == 2:
        garment_2 = garment_2_and_layout_description or DEFAULTS.garment_duo

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


__all__ = [
    "PROMPT_TEMPLATE",
    "DEFAULTS",
    "PromptDefaults",
    "build_virtual_tryon_prompt",
]
