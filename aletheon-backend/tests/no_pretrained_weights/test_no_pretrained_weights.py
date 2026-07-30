"""
No Pretrained Weights Compliance Test — Release Gate

Statically scans the codebase, requirements.txt, and active python imports
for known pretrained-model entry points:
  - sentence_transformers
  - llama_cpp
  - transformers.AutoModel*
  - .from_pretrained(
  - HuggingFace Hub URL patterns (huggingface.co/...)
  - GGUF file references

Documented exception:
  - pytesseract / eng.traineddata (OCR character recognition)

Fails the build if any forbidden entry point is found outside the documented exception.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
APP_DIR = PROJECT_ROOT / "app"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REQ_FILE = PROJECT_ROOT / "requirements.txt"

FORBIDDEN_IMPORTS = [
    "sentence_transformers",
    "llama_cpp",
    "transformers",
    "huggingface_hub",
    "torch",
    "torchvision",
    "faiss",
]

FORBIDDEN_PATTERNS = [
    re.compile(r"\bAutoModel\w*\b"),
    re.compile(r"\.from_pretrained\s*\("),
    re.compile(r"https?://huggingface\.co/"),
    re.compile(r"\.gguf\b", re.IGNORECASE),
    re.compile(r"SentenceTransformer\s*\("),
]


def test_requirements_txt_has_no_pretrained_deps():
    """requirements.txt must not contain sentence-transformers, torch, llama-cpp, or faiss."""
    assert REQ_FILE.exists(), "requirements.txt missing"
    content = REQ_FILE.read_text(encoding="utf-8")
    for dep in FORBIDDEN_IMPORTS:
        matches = [line for line in content.splitlines() if line.strip() and not line.strip().startswith("#") and dep in line]
        assert not matches, f"Forbidden dependency '{dep}' found in requirements.txt: {matches}"


def test_codebase_has_no_pretrained_imports():
    """Python files in app/ must not import pretrained model libraries."""
    py_files = list(APP_DIR.glob("**/*.py"))
    assert py_files, "No python files found in app/"

    violations = []
    for p in py_files:
        content = p.read_text(encoding="utf-8")
        for dep in FORBIDDEN_IMPORTS:
            # Check import lines
            pattern = re.compile(rf"^\s*(?:import|from)\s+{dep}\b", re.MULTILINE)
            if pattern.search(content):
                violations.append((p.relative_to(PROJECT_ROOT), dep))

    assert not violations, f"Forbidden imports detected in app/: {violations}"


def test_codebase_has_no_pretrained_patterns():
    """Python files in app/ must not contain AutoModel, .from_pretrained, GGUF, or HF URLs."""
    py_files = list(APP_DIR.glob("**/*.py"))
    violations = []

    for p in py_files:
        content = p.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            if pat.search(content):
                violations.append((p.relative_to(PROJECT_ROOT), pat.pattern))

    assert not violations, f"Forbidden pretrained model patterns detected in app/: {violations}"


def test_config_flags_pretrained_weights_false():
    """Settings.PRETRAINED_WEIGHTS_USED must be False."""
    from app.config import settings
    assert settings.PRETRAINED_WEIGHTS_USED is False, "PRETRAINED_WEIGHTS_USED flag must be False"
