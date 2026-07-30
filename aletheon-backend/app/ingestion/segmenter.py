"""Structural segmenter — converts ExtractedBlocks into SourceSpans with stable IDs."""
from __future__ import annotations

from typing import List

from app.ingestion.pdf_parser import ExtractedBlock
from app.models.schemas import SourceSpan


def segment_blocks(doc_id: str, blocks: List[ExtractedBlock]) -> List[SourceSpan]:
    """
    Assign a stable source_id to each block.

    Format: {doc_id}_p{page}_s{section_idx}_p{paragraph_idx}
            {doc_id}_p{page}_s{section_idx}_h   (for section headers)

    Counters reset per section; section index increments on every header.
    """
    spans: List[SourceSpan] = []
    section_idx = 0
    par_idx = 0
    current_section: str | None = None

    for blk in blocks:
        if blk.block_type == "header":
            section_idx += 1
            par_idx = 0
            current_section = blk.text
            source_id = f"{doc_id}_p{blk.page_num}_s{section_idx}_h"
            spans.append(SourceSpan(
                source_id=source_id,
                document_id=doc_id,
                page=blk.page_num,
                section=current_section,
                paragraph_offset=0,
                text=blk.text,
            ))
        else:
            par_idx += 1
            btype_tag = {"figure": "f", "table": "t"}.get(blk.block_type, "p")
            source_id = f"{doc_id}_p{blk.page_num}_s{section_idx}_{btype_tag}{par_idx}"
            spans.append(SourceSpan(
                source_id=source_id,
                document_id=doc_id,
                page=blk.page_num,
                section=current_section,
                paragraph_offset=par_idx,
                text=blk.text,
            ))

    return spans
