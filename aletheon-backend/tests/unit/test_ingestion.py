"""Unit tests for ingestion pipeline — parser, segmenter, source_id stability."""
import pytest
from app.ingestion.pdf_parser import ExtractedBlock
from app.ingestion.segmenter import segment_blocks


def test_segmenter_basic():
    blocks = [
        ExtractedBlock(page_num=1, block_type="header",    text="Introduction"),
        ExtractedBlock(page_num=1, block_type="paragraph", text="First paragraph."),
        ExtractedBlock(page_num=2, block_type="paragraph", text="Second on page 2."),
        ExtractedBlock(page_num=2, block_type="header",    text="Methods"),
        ExtractedBlock(page_num=2, block_type="paragraph", text="Method paragraph."),
        ExtractedBlock(page_num=2, block_type="figure",    text="[Figure]"),
    ]
    spans = segment_blocks("doc1", blocks)

    assert len(spans) == 6

    # Header gets _h suffix
    assert spans[0].source_id == "doc1_p1_s1_h"
    assert spans[0].section == "Introduction"

    # Paragraphs count within section
    assert spans[1].source_id == "doc1_p1_s1_p1"

    # New section resets counter
    assert spans[3].source_id == "doc1_p2_s2_h"
    assert spans[4].source_id == "doc1_p2_s2_p1"

    # Figure gets _f prefix
    assert spans[5].source_id == "doc1_p2_s2_f2"


def test_source_ids_are_unique():
    blocks = [
        ExtractedBlock(page_num=i // 3 + 1, block_type="paragraph", text=f"Para {i}")
        for i in range(15)
    ]
    spans = segment_blocks("docX", blocks)
    ids = [s.source_id for s in spans]
    assert len(ids) == len(set(ids)), "Duplicate source_ids detected"


def test_segmenter_all_paragraphs_have_text():
    blocks = [ExtractedBlock(page_num=1, block_type="paragraph", text="Some text.")]
    spans = segment_blocks("d", blocks)
    assert all(s.text for s in spans)
