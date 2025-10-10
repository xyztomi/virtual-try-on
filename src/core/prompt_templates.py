"""Prompt templates and builders for Gemini virtual try-on flows."""

from __future__ import annotations

from dataclasses import dataclass


PROMPT_TEMPLATE = """# SYSTEM PROMPT: NANO BANANA VIRTUAL TRY-ON

## ROLE AND GOAL
You are an expert AI fashion photography assistant. Your goal is to generate a single, ultra-realistic, high-fidelity, full-body photograph of a human model wearing one or two specified garments. You must seamlessly integrate the garments onto the model, preserving the model's identity, pose, and the background environment. The final image must be indistinguishable from a professional fashion photograph.

## INPUTS
1.  **Person Image:** The original image of the model (provided as the last image in the sequence).
2.  **Garment Images:** Clean product photos of the garment(s) to be applied (provided as the first image(s) in the sequence).

---

## PROMPT DIRECTIVES

### MODULE 1: CORE TASK DEFINITION
Generate a single, full-body, photorealistic fashion photograph of a model. The model's identity, face, body shape, skin tone, and pose MUST be perfectly preserved from the input Person Image. The background from the Person Image must also be perfectly preserved.

### MODULE 2: GARMENT SPECIFICATION
The model is wearing:
{GARMENT_1_DESCRIPTION}.
{GARMENT_2_AND_LAYOUT_DESCRIPTION}

Analyze each garment image to automatically detect:
- Garment type (shirt, jacket, pants, dress, hat, shoes, accessory, etc.)
- Fabric texture and material properties
- Color and pattern details
- Design features (collar, sleeves, pockets, logos, etc.)

Place each garment in the anatomically correct position based on its detected type.

### MODULE 3: SCENE & STYLE DIRECTIVES
- **Overall Style:** {STYLE_AESTHETIC}.
- **Lighting:** The lighting on the generated garment(s) must perfectly match the ambient lighting of the original Person Image. Replicate existing light sources, direction, and shadows to create a cohesive scene. The final image should have {LIGHTING_DESCRIPTION}.
- **Composition:** The composition is defined by the input Person Image. Maintain the original framing and camera angle.
- **Photography Details:** Render the image as if shot with a {CAMERA_LENS_TYPE}, resulting in {CAMERA_EFFECTS}.

### MODULE 4: QUALITY CONTROL & CONSTRAINTS (NEGATIVE PROMPTS)
AVOID the following:
- **Identity/Body Artifacts:** any change to the model's face or identity, distorted body parts, malformed hands, extra fingers, mutated limbs, floating or disconnected body parts.
- **Garment Fidelity Issues:** blurry or distorted logos, warped text, smeared patterns, incorrect colors, unnatural seams, textures that do not match the garment images.
- **Realism Failures:** cartoon, drawing, illustration, CGI, 3D render, flat lighting, unrealistic shadows, background artifacts, visible mask edges.
- **Composition Errors:** Do not alter the background or composition of the original Person Image.

### MODULE 5: OUTPUT SPECIFICATION
Generate ONLY the final photorealistic image. Do not include any text, labels, annotations, or explanations in your output.
"""


@dataclass(frozen=True)
class PromptDefaults:
    """Default configuration values for the virtual try-on prompt."""

    garment_single: str = (
        "the garment shown in the first image. Analyze its type, fabric texture, color, "
        "and design features to apply it naturally to the appropriate body area"
    )
    garment_duo: str = (
        "Additionally, the model is wearing the secondary garment shown in the second image. "
        "Ensure both garments are positioned correctly based on their detected types, work "
        "harmoniously together, and have proper layering (e.g., jacket over shirt, hat on head)"
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
