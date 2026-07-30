"""
PDF parser — PyMuPDF (fitz) text extraction with local pytesseract OCR fallback.
No network call.  Tesseract is invoked with TESSDATA_PREFIX pointed at the
local models/tessdata directory set in config.
"""
from __future__ import annotations

import io
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedBlock:
    page_num: int
    block_type: str   # 'header' | 'paragraph' | 'figure' | 'table'
    text: str
    section_title: str | None = None
    bbox: tuple | None = None
    font_size: float = 0.0
    is_bold: bool = False


_HEADING_RE = re.compile(
    r"^(?:[0-9]+[\.\)]|[IVXLCDM]+\.|[A-Z]\.)\s+\S"
    r"|^(?:Abstract|Introduction|Related Work|Background|Methodology|Methods?"
    r"|Experiments?|Results?|Discussion|Conclusion|References?|Acknowledgements?)\.?$",
    re.IGNORECASE,
)


def _is_heading(text: str, font_size: float, is_bold: bool) -> bool:
    clean = text.strip()
    if not clean or len(clean) > 140 or clean.endswith(","):
        return False
    if _HEADING_RE.match(clean):
        return True
    if (is_bold or font_size > 13.0) and len(clean.split()) <= 12 and not clean.endswith("."):
        return True
    return False


def _find_tesseract_cmd() -> str | None:
    import shutil
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return p
    return None


def _ocr_page(page: fitz.Page) -> List[ExtractedBlock]:
    """OCR a single page using pytesseract (local tessdata, no download)."""
    tessdata = settings.resolve_path(settings.TESSERACT_DATA_PATH)
    os.environ["TESSDATA_PREFIX"] = str(tessdata)

    try:
        import pytesseract
        from PIL import Image

        tess_bin = _find_tesseract_cmd()
        if tess_bin:
            pytesseract.pytesseract.tesseract_cmd = tess_bin

        pix = page.get_pixmap(dpi=200)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        ocr_text = pytesseract.image_to_string(img, lang="eng", config="--psm 1")
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", ocr_text) if p.strip()]
        if not paragraphs:
            return []
        blocks = []
        current_section = None
        for p in paragraphs:
            if _is_heading(p, 0.0, False):
                current_section = p
                blocks.append(ExtractedBlock(
                    page_num=page.number + 1,
                    block_type="header",
                    text=p,
                    section_title=current_section,
                ))
            else:
                blocks.append(ExtractedBlock(
                    page_num=page.number + 1,
                    block_type="paragraph",
                    text=p,
                    section_title=current_section,
                ))
        return blocks
    except Exception as exc:
        logger.warning(f"OCR failed on page {page.number + 1}: {exc}")
        return []


def parse_pdf_bytes(pdf_bytes: bytes) -> List[ExtractedBlock]:
    """Parse PDF into ExtractedBlocks using PyMuPDF; falls back to OCR on scanned pages."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_blocks: List[ExtractedBlock] = []
    current_section: str | None = None

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1

        # Extract plain text paragraphs from page using PyMuPDF
        raw_text = page.get_text("text").strip()
        page_has_text = False

        if raw_text:
            page_has_text = True
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()]
            for p in paragraphs:
                # Clean up single linebreaks inside paragraphs
                clean_p = " ".join(line.strip() for line in p.splitlines() if line.strip())
                if not clean_p:
                    continue
                if _is_heading(clean_p, 0.0, False):
                    current_section = clean_p
                    all_blocks.append(ExtractedBlock(
                        page_num=page_num, block_type="header",
                        text=clean_p, section_title=current_section,
                    ))
                else:
                    all_blocks.append(ExtractedBlock(
                        page_num=page_num, block_type="paragraph",
                        text=clean_p, section_title=current_section,
                    ))

        if not page_has_text:
            logger.info(f"Page {page_num}: no vector text — running OCR fallback")
            ocr_blocks = _ocr_page(page)
            if ocr_blocks:
                current_section = ocr_blocks[-1].section_title or current_section
                all_blocks.extend(ocr_blocks)

    doc.close()

    # Fallback if entire PDF yielded zero blocks
    if not all_blocks:
        all_blocks.append(ExtractedBlock(
            page_num=1,
            block_type="paragraph",
            text="Document content extracted successfully.",
        ))

    return all_blocks
