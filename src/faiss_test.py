"""Build a FAISS index over the processed commits, try some searches, and benchmark.

Run from the project root:
    python ./src/faiss_test.py            # real OpenAI embeddings (needs OPENAI_API_KEY)
    python ./src/faiss_test.py --offline  # free local hashing embedder, no API key (lower quality)
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
import os

from vector_store.faiss_index import CommitVectorStore, INDEX_TYPES, _normalize

# All paths in this project are relative to the project root, so run from there
# no matter where the script was launched.
os.chdir(Path(__file__).resolve().parent.parent)

COMMITS_FILE = Path("checkpoint_factual/checkpoint_2/tqdm_all_processed_commits.json")
OUT_DIR = Path("checkpoint_factual/checkpoint_3")

QUERIES = [
    "fix progress bar rendering in notebooks",
    "when was python 2 support dropped",
    "changes to CI and GitHub workflows",
    "bug with unicode or ascii output",
    "new release version bump",
]


def hashing_embedder(dim: int = 512):
    """Offline stand-in for OpenAI embeddings: bag-of-words hashed into `dim` buckets.
    Only captures word overlap (no meaning), but it is deterministic and free."""
    def embed(texts):
        out = np.zeros((len(texts), dim), dtype="float32")
        for row, text in enumerate(texts):
            for tok in re.findall(r"[a-z0-9_]+", text.lower()):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[row, h % dim] += 1.0
        return out.tolist()
    return embed


def benchmark(embed_fn, commits, name: str, n_queries: int = 200, k: int = 5):
    """Compare index types: build time, per-query latency, and recall vs exact search."""
    rng = np.random.default_rng(0)
    results = {}
    exact_ids = None
    query_vecs = None

    for index_type in INDEX_TYPES:  # "flat" first, so it is the ground truth
        # Same name as the main store so the cached embeddings are reused (no extra API cost).
        store = CommitVectorStore(embed_fn, name=name, index_type=index_type)
        store.build(commits, save=False)

        if query_vecs is None:
            matrix = _normalize(np.load(store._emb_path))
            picks = rng.choice(len(matrix), size=min(n_queries, len(matrix)), replace=False)
            query_vecs = matrix[picks]

        latencies = []
        all_ids = []
        for q in query_vecs:  # one query at a time, like a real request
            t0 = time.perf_counter()
            _, ids = store.index.search(q[None, :], k)
            latencies.append((time.perf_counter() - t0) * 1000)
            all_ids.append(ids[0])
        all_ids = np.array(all_ids)

        if exact_ids is None:
            exact_ids = all_ids
        recall = float(np.mean([len(set(a) & set(b)) / k for a, b in zip(all_ids, exact_ids)]))

        results[index_type] = {
            "index_build_ms": round(store.timings["index_build_s"] * 1000, 2),
            "query_mean_ms": round(float(np.mean(latencies)), 4),
            "query_p99_ms": round(float(np.percentile(latencies, 99)), 4),
            "query_max_ms": round(float(np.max(latencies)), 4),
            f"recall_at_{k}_vs_flat": round(recall, 4),
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    with open(COMMITS_FILE, "r", encoding="utf-8") as f:
        commits = json.load(f)
    print(f"Loaded {len(commits)} commits")

    if args.offline:
        embed_fn, name = hashing_embedder(), "tqdm_offline"
    else:
        from llm_api.llm_client import LLMClient
        load_dotenv()
        embed_fn, name = LLMClient(os.getenv("OPENAI_API_KEY")).embed, "tqdm"

    store = CommitVectorStore(embed_fn, name=name, index_type="flat")
    if not store.load():
        store.build(commits)
        print(f"Embedded in {store.timings['embed_s']:.2f}s, "
              f"index built in {store.timings['index_build_s'] * 1000:.1f}ms")
    else:
        print("Loaded saved index from disk")

    output = {"n_commits": len(commits), "searches": [], "benchmark": None}
    for q in QUERIES:
        hits = store.search(q, k=3)
        print(f"\nQ: {q}  (embed {store.timings['query_embed_s'] * 1000:.1f}ms, "
              f"search {store.timings['query_search_s'] * 1000:.3f}ms)")
        for h in hits:
            print(f"  {h['rank']}. [{h['score']:.3f}] {h['sha'][:8]} {h['date'][:10]} "
                  f"{h['message'].splitlines()[0][:70]}")
        output["searches"].append({
            "query": q,
            "hits": [{"sha": h["sha"], "score": h["score"], "message": h["message"].splitlines()[0]}
                     for h in hits],
        })

    print("\nBenchmark (per-query FAISS latency only, queries sampled from the commits):")
    output["benchmark"] = benchmark(embed_fn, commits, name)
    for index_type, r in output["benchmark"].items():
        print(f"  {index_type:5s} {r}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUT_DIR / f"faiss_results_{name}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved {out_file}")


if __name__ == "__main__":
    main()