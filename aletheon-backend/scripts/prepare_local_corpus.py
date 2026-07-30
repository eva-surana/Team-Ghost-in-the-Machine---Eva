"""
prepare_local_corpus.py — Helper to assemble or index recommendation corpus papers.

Usage:
  python scripts/prepare_local_corpus.py [--corpus-dir ./corpus] [--output ./models/corpus_index.pkl]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.recommendation.corpus_index import CorpusIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble & index local recommendation corpus")
    parser.add_argument("--corpus-dir", default="./corpus", help="Path to corpus directory containing papers.json")
    parser.add_argument("--output", default="./models/corpus_index.pkl", help="Output path for corpus_index.pkl")
    args = parser.parse_args()

    corpus_dir = Path(args.corpus_dir).resolve()
    output_path = Path(args.output).resolve()

    print("=" * 60)
    print("  Aletheon — Building Recommendation Corpus Index")
    print("=" * 60)
    print(f"[*] Reading corpus from: {corpus_dir}")

    try:
        index = CorpusIndex.build(corpus_dir)
        index.save(output_path)
        print(f"✓ Corpus index saved to {output_path} ({index.paper_count} papers indexed)")
    except Exception as exc:
        print(f"✗ Failed to build corpus index: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
