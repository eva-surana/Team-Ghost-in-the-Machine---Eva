"""
prepare_offline_bundle.py — Phase A (run ONCE on any machine, networked for convenience)

This script builds and vendors all self-trained artifacts required to run Aletheon
on an air-gapped laptop with ZERO pretrained weights:
  1. Trains the self-trained entailment classifier (models/entailment_classifier.pkl)
  2. Builds the TF-IDF recommendation corpus index (models/corpus_index.pkl)
  3. Downloads Tesseract eng.traineddata language pack (documented narrow exception)
  4. Builds full pip wheelhouse (wheelhouse/) for offline installation

NO pretrained model weights are downloaded anywhere by this script.

Usage:
  python scripts/prepare_offline_bundle.py [--models-dir ./models] [--wheels-dir ./wheelhouse]
"""

import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata/raw/main/eng.traineddata"


def train_classifier(models_dir: Path) -> None:
    """Train self-trained LogisticRegression entailment classifier."""
    print("\n[+] Training self-trained Entailment Classifier...")
    from app.verification.train_entailment_classifier import train

    training_data = PROJECT_ROOT / "training_data" / "entailment_triples.jsonl"
    dest = models_dir / "entailment_classifier.pkl"
    train(training_data_path=training_data, output_path=dest)


def build_corpus_index(models_dir: Path) -> None:
    """Build TF-IDF corpus recommendation index."""
    print("\n[+] Building Corpus Recommendation Index...")
    from app.recommendation.corpus_index import CorpusIndex

    corpus_dir = PROJECT_ROOT / "corpus"
    dest = models_dir / "corpus_index.pkl"
    idx = CorpusIndex.build(corpus_dir)
    idx.save(dest)
    print(f"    OK: Saved corpus index with {idx.paper_count} papers to {dest}")


def download_tessdata(models_dir: Path) -> None:
    """Download Tesseract English language data (documented OCR exception)."""
    tessdata_dir = models_dir / "tessdata"
    tessdata_dir.mkdir(parents=True, exist_ok=True)
    dest = tessdata_dir / "eng.traineddata"
    if dest.exists():
        print(f"[=] Tessdata already at {dest} — skipping")
        return
    print(f"\n[+] Downloading Tesseract eng.traineddata (documented OCR exception)")
    try:
        urllib.request.urlretrieve(TESSDATA_URL, str(dest))
        print(f"    OK: Saved to {dest}")
    except Exception as exc:
        print(f"    WARNING: Tessdata download failed: {exc}. OCR fallback will require local tessdata.")


def build_wheelhouse(wheels_dir: Path, requirements_path: Path) -> None:
    """pip download all requirements into a local wheelhouse directory."""
    wheels_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[+] Building wheelhouse at {wheels_dir}")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--dest",
            str(wheels_dir),
            "--prefer-binary",
            "-r",
            str(requirements_path),
        ],
        capture_output=False,
    )
    if result.returncode != 0:
        print("    FAIL: pip download failed")
        sys.exit(1)
    print(f"    OK: Wheelhouse ready at {wheels_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Aletheon offline self-trained bundle")
    parser.add_argument("--models-dir", default="./models", help="Destination for trained artifacts")
    parser.add_argument("--wheels-dir", default="./wheelhouse", help="Destination for pip wheels")
    parser.add_argument("--skip-wheels", action="store_true", help="Skip wheelhouse build")
    args = parser.parse_args()

    models_dir = Path(args.models_dir).resolve()
    wheels_dir = Path(args.wheels_dir).resolve()
    req_file = PROJECT_ROOT / "requirements.txt"

    print("=" * 60)
    print("  Aletheon -- Phase A Bundle Preparation (Zero Pretrained Weights)")
    print("=" * 60)

    models_dir.mkdir(parents=True, exist_ok=True)
    train_classifier(models_dir)
    build_corpus_index(models_dir)
    download_tessdata(models_dir)

    if not args.skip_wheels:
        build_wheelhouse(wheels_dir, req_file)

    print("\n" + "=" * 60)
    print("  Bundle preparation complete!")
    print(f"  Trained Artifacts: {models_dir}")
    print(f"  Wheelhouse:        {wheels_dir}")
    print("\n  Transfer both directories to the air-gapped machine, then run:")
    print("  pip install --no-index --find-links=./wheelhouse -r requirements.txt")
    print("=" * 60)


if __name__ == "__main__":
    main()
