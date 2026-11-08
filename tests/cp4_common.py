"""Shared setup for the Checkpoint 4 scripts (run them from the repo root)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))  # new CP4 packages work even without re-running pip install -e .

NEWEST_SHA = "d6ad58fe5ef7b1e838d8078963d9e890e32f3985"  # v3.1.4
OLDEST_SHA = "4d7aac956b414dd396ac807a8b19f30be15711ee"  # v2.0.0
OUT_DIR = ROOT / "tests" / "test_output" / "cp4"


def make_embedder(name: str):
    """bge-m3 is the real embedder. 'hashing' is a tiny offline stand-in used only to
    smoke-test the scripts on a machine without the model; its numbers are not reported."""
    if name == "bge-m3":
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3", local_files_only=True)
        return lambda texts: model.encode(texts, batch_size=8, show_progress_bar=len(texts) > 50).tolist()
    if name == "hashing":
        from sklearn.feature_extraction.text import HashingVectorizer
        vec = HashingVectorizer(n_features=4096, alternate_sign=False, ngram_range=(1, 2), stop_words="english")
        return lambda texts: vec.transform(texts).toarray().tolist()
    raise ValueError(name)
