"""
Image transformation functions for the PhotoMind AI Synthetic Dataset Generator.

Each function takes a PIL Image and TransformParams, applies a randomized
transformation, and returns the modified image along with metadata describing
what was applied. EXIF data is preserved where possible.
"""

import random
import logging
from typing import Dict, Any, Tuple, Optional

from PIL import Image, ImageFilter, ImageEnhance, ExifTags

from .config import TransformParams

logger = logging.getLogger("dataset_generator.transforms")


def _extract_exif(img: Image.Image) -> Optional[bytes]:
    """
    Extract raw EXIF bytes from an image if present.

    Returns:
        Raw EXIF bytes or None if no EXIF data exists.
    """
    try:
        exif_data = img.info.get("exif")
        if exif_data:
            return exif_data
    except Exception:
        pass
    return None


def _save_with_exif(
    img: Image.Image,
    output_path: str,
    exif_bytes: Optional[bytes] = None,
    quality: int = 92,
) -> None:
    """
    Save image to disk, embedding EXIF data if available.

    Args:
        img: PIL Image to save.
        output_path: Destination file path.
        exif_bytes: Raw EXIF bytes to embed.
        quality: JPEG compression quality (1-100).
    """
    save_kwargs: Dict[str, Any] = {"quality": quality}
    if exif_bytes:
        save_kwargs["exif"] = exif_bytes

    # Ensure RGB mode for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    img.save(output_path, "JPEG", **save_kwargs)


def exact_duplicate(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Return an identical copy of the image (byte-level duplicate).

    Args:
        img: Source PIL Image.
        params: Transform parameters (unused for duplicates).

    Returns:
        Tuple of (copied image, metadata dict).
    """
    return img.copy(), {"transform": "exact_duplicate"}


def resize_compress(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Resize the image to a random smaller scale and apply heavy JPEG compression.

    Args:
        img: Source PIL Image.
        params: Controls scale range and JPEG quality range.

    Returns:
        Tuple of (resized image, metadata dict with scale and quality).
    """
    scale = random.uniform(params.resize_scale_min, params.resize_scale_max)
    new_width = max(1, int(img.width * scale))
    new_height = max(1, int(img.height * scale))
    quality = random.randint(params.jpeg_quality_min, params.jpeg_quality_max)

    resized = img.resize((new_width, new_height), Image.LANCZOS)
    metadata = {
        "transform": "resize_compress",
        "scale": round(scale, 3),
        "new_size": f"{new_width}x{new_height}",
        "quality": quality,
    }
    return resized, metadata


def gaussian_blur(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Apply Gaussian blur with a random radius.

    Args:
        img: Source PIL Image.
        params: Controls blur radius range.

    Returns:
        Tuple of (blurred image, metadata dict with radius).
    """
    radius = random.uniform(params.blur_radius_min, params.blur_radius_max)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return blurred, {"transform": "gaussian_blur", "radius": round(radius, 2)}


def darken(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Reduce image brightness to simulate underexposure.

    Args:
        img: Source PIL Image.
        params: Controls brightness reduction factor range.

    Returns:
        Tuple of (darkened image, metadata dict with factor).
    """
    factor = random.uniform(params.darken_factor_min, params.darken_factor_max)
    enhancer = ImageEnhance.Brightness(img)
    darkened = enhancer.enhance(factor)
    return darkened, {"transform": "darken", "brightness_factor": round(factor, 3)}


def brighten(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Increase image brightness to simulate overexposure.

    Args:
        img: Source PIL Image.
        params: Controls brightness increase factor range.

    Returns:
        Tuple of (brightened image, metadata dict with factor).
    """
    factor = random.uniform(params.brighten_factor_min, params.brighten_factor_max)
    enhancer = ImageEnhance.Brightness(img)
    brightened = enhancer.enhance(factor)
    return brightened, {"transform": "brighten", "brightness_factor": round(factor, 3)}


def rotate(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Rotate the image by a fixed angle (90/180/270) or a random arbitrary angle.

    Fixed rotations preserve image dimensions exactly.
    Arbitrary rotations expand the canvas to fit the rotated content.

    Args:
        img: Source PIL Image.
        params: Controls rotation angles and arbitrary rotation probability.

    Returns:
        Tuple of (rotated image, metadata dict with angle and type).
    """
    if random.random() < params.arbitrary_rotation_chance:
        # Arbitrary angle rotation with canvas expansion
        angle = random.uniform(
            params.arbitrary_rotation_min, params.arbitrary_rotation_max
        )
        # Randomly choose clockwise or counterclockwise
        if random.random() < 0.5:
            angle = -angle
        rotated = img.rotate(angle, expand=True, fillcolor=(0, 0, 0))
        return rotated, {
            "transform": "rotate",
            "angle": round(angle, 1),
            "type": "arbitrary",
        }
    else:
        # Fixed cardinal rotation (lossless dimension swap)
        angle = random.choice(params.rotation_angles)
        rotated = img.rotate(angle, expand=True)
        return rotated, {
            "transform": "rotate",
            "angle": angle,
            "type": "cardinal",
        }


def random_crop(
    img: Image.Image, params: TransformParams
) -> Tuple[Image.Image, Dict[str, Any]]:
    """
    Crop a random rectangular region from the image.

    The crop size is a random fraction of the original dimensions,
    positioned randomly within the image bounds.

    Args:
        img: Source PIL Image.
        params: Controls crop ratio range (fraction of original size).

    Returns:
        Tuple of (cropped image, metadata dict with crop box and ratio).
    """
    ratio = random.uniform(params.crop_ratio_min, params.crop_ratio_max)
    crop_width = max(1, int(img.width * ratio))
    crop_height = max(1, int(img.height * ratio))

    # Random position within bounds
    max_x = max(0, img.width - crop_width)
    max_y = max(0, img.height - crop_height)
    x = random.randint(0, max_x)
    y = random.randint(0, max_y)

    cropped = img.crop((x, y, x + crop_width, y + crop_height))
    return cropped, {
        "transform": "random_crop",
        "crop_box": f"({x},{y},{x + crop_width},{y + crop_height})",
        "crop_ratio": round(ratio, 3),
        "crop_size": f"{crop_width}x{crop_height}",
    }


# ─── Registry ───────────────────────────────────────────────────────────
# Maps category names to their transform functions for the generator to use.
TRANSFORM_REGISTRY = {
    "duplicates": exact_duplicate,
    "resized": resize_compress,
    "blurred": gaussian_blur,
    "dark": darken,
    "bright": brighten,
    "rotated": rotate,
    "cropped": random_crop,
}
