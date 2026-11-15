import io
import math
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None


def calculate_relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculates relative luminance for an sRGB tuple based on WCAG 2.1 specs."""
    vals = []
    for c in rgb[:3]:
        c_norm = c / 255.0
        if c_norm <= 0.03928:
            vals.append(c_norm / 12.92)
        else:
            vals.append(((c_norm + 0.055) / 1.055) ** 2.4)
    return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]


def calculate_contrast_ratio(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    """Calculates WCAG 2.1 contrast ratio between two colors (L1 + 0.05) / (L2 + 0.05)."""
    l1 = calculate_relative_luminance(color1)
    l2 = calculate_relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


class ImageInspectionResult:
    def __init__(
        self,
        width: int,
        height: int,
        aspect_ratio: float,
        ocr_text: str = "",
        dominant_colors: Optional[List[Tuple[int, int, int]]] = None,
        min_contrast_ratio: Optional[float] = None,
    ):
        self.width = width
        self.height = height
        self.aspect_ratio = aspect_ratio
        self.ocr_text = ocr_text
        self.dominant_colors = dominant_colors or []
        self.min_contrast_ratio = min_contrast_ratio


def inspect_image_bytes(image_bytes: bytes) -> ImageInspectionResult:
    """
    Analyzes image bytes: dimensions, aspect ratio, OCR text extraction,
    and estimated background/foreground contrast ratio.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    aspect_ratio = round(width / float(height), 4) if height > 0 else 1.0

    # OCR text extraction
    ocr_text = ""
    if pytesseract:
        try:
            ocr_text = pytesseract.image_to_string(img).strip()
        except Exception:
            # Tesseract binary not installed on OS, fallback gracefully
            ocr_text = ""

    # Dominant colors & contrast estimation
    # Resize to thumbnail for fast color analysis
    thumb = img.resize((32, 32))
    colors = thumb.getcolors(maxcolors=1024) or []
    colors.sort(key=lambda x: x[0], reverse=True)
    dominant_rgb = [c[1] for c in colors[:5]]

    min_contrast = None
    if len(dominant_rgb) >= 2:
        # Compare most dominant (likely background) to second dominant (foreground)
        min_contrast = calculate_contrast_ratio(dominant_rgb[0], dominant_rgb[1])

    return ImageInspectionResult(
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        ocr_text=ocr_text,
        dominant_colors=dominant_rgb,
        min_contrast_ratio=min_contrast,
    )
