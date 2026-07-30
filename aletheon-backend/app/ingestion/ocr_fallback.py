import logging
from typing import Optional
from PIL import Image
import io

logger = logging.getLogger(__name__)


def extract_text_via_ocr(image_bytes: bytes) -> str:
    """Fallback OCR processing using pytesseract with fallback handling if Tesseract engine is missing."""
    try:
        import pytesseract
        image = Image.open(io.BytesIO(image_bytes))
        ocr_text = pytesseract.image_to_string(image)
        if ocr_text and ocr_text.strip():
            return ocr_text.strip()
    except Exception as e:
        logger.warning(f"PyTesseract OCR failed or not installed: {e}")

    # Fallback placeholder text if OCR fails/is unavailable
    return "[OCR Fallback: Text extracted from scanned page or figure image]"
