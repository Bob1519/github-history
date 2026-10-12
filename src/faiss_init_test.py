"""FAISS initialization demo: a vector database holding a handful of random words.

No API key needed. Run from the project root:
    python ./src/faiss_init_test.py

What this shows:
  1. Create a FAISS index
  2. Turn words into vectors and add them to the index
  3. Search the index with a query word
  4. Save the index to disk and load it back, getting identical results

Real commit embeddings and chunking come in a later checkpoint; the index
mechanics here are the same ones that will be used then.
"""
import json
from pathlib import Path

import faiss
import numpy as np

DIM = 64
WORDS = [
    "apple", "apples", "banana", "orange", "grape", "lemon",
    "river", "rivet", "rover", "mountain", "ocean", "forest",
    "commit", "committee", "merge", "branch", "branching", "release",
    "python", "pythons", "pylon", "tqdm", "progress", "process",
]
QUERIES = ["apple", "commits", "branches", "rive", "pythonic"]

OUT_DIR = Path("checkpoint_factual/checkpoint_2")
INDEX_FILE = OUT_DIR / "words.faiss"
RESULTS_FILE = OUT_DIR / "faiss_init_results.json"


def word_to_vector(word: str) -> np.ndarray:
    """Placeholder embedding: hash the word's character trigrams into DIM buckets.
    Words with similar spelling end up close together. This is NOT a semantic
    model, just enough to exercise the vector database."""
    padded = f"^{word.lower()}$"
    vec = np.zeros(DIM, dtype="float32")
    for i in range(len(padded) - 2):
        # Python's hash() is randomized per run, so use a stable one instead.
        h = 0
        for ch in padded[i:i + 3]:
            h = (h * 131 + ord(ch)) % 1_000_003
        vec[h % DIM] += 1.0
    return vec


def search(index, words, query, k=3):
    q = word_to_vector(query)[None, :]
    faiss.normalize_L2(q)
    scores, ids = index.search(q, k)
    return [{"word": words[i], "score": round(float(s), 4)} for s, i in zip(scores[0], ids[0])]


def main():
    # 1. Create the index. Inner product on L2-normalized vectors == cosine similarity.
    index = faiss.IndexFlatIP(DIM)

    # 2. Embed the words and add them. FAISS only stores vectors, so `WORDS`
    #    is our id -> word lookup: row i of the index is WORDS[i].
    vectors = np.stack([word_to_vector(w) for w in WORDS])
    faiss.normalize_L2(vectors)
    index.add(vectors)
    print(f"Index created: dim={index.d}, vectors stored={index.ntotal}")

    # 3. Search.
    results = {}
    for q in QUERIES:
        results[q] = search(index, WORDS, q)
        print(f"{q!r:12} -> {results[q]}")

    # 4. Save, reload, and confirm the reloaded index gives the same answers.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_FILE))
    reloaded = faiss.read_index(str(INDEX_FILE))
    same = all(search(reloaded, WORDS, q) == results[q] for q in QUERIES)
    print(f"Saved to {INDEX_FILE} ({INDEX_FILE.stat().st_size} bytes); "
          f"reloaded index matches original: {same}")
    assert reloaded.ntotal == index.ntotal and same

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "faiss_version": faiss.__version__,
            "index_type": "IndexFlatIP",
            "dim": DIM,
            "n_vectors": index.ntotal,
            "words": WORDS,
            "searches": results,
            "reload_matches": same,
        }, f, indent=2)
    print(f"Saved {RESULTS_FILE}")


if __name__ == "__main__":
    main()
