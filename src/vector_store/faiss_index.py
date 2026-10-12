"""FAISS-backed semantic search over processed commits.

Pipeline position:
    GitHubAPI.get_all_processed_commits()  ->  CommitVectorStore.build()
    user question                          ->  CommitVectorStore.search()  ->  top-k commits -> LLM

Each commit dict (as produced by GitHubAPI.parse_commit) has an "embedding_text"
field. We embed that text, put the vectors in a FAISS index, and keep a parallel
list of commits, because FAISS only returns row numbers (positions), not SHAs.
Row i of the index == self.commits[i].
"""
import hashlib
import json
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import faiss
import numpy as np

# embed_fn takes a list of strings and returns one vector per string.
# In the real pipeline this is LLMClient.embed.
EmbedFn = Callable[[List[str]], List[List[float]]]

INDEX_TYPES = ("flat", "hnsw", "ivf")


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    """float32, L2-normalized copy. With unit vectors, inner product == cosine similarity."""
    vectors = np.ascontiguousarray(vectors, dtype="float32")
    faiss.normalize_L2(vectors)
    return vectors


class CommitVectorStore:
    def __init__(self, embed_fn: EmbedFn, name: str = "repo",
                 index_dir: Path = Path("faiss_cache"), index_type: str = "flat"):
        if index_type not in INDEX_TYPES:
            raise ValueError(f"index_type must be one of {INDEX_TYPES}")
        self.embed_fn = embed_fn
        self.name = name
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_type = index_type

        self.index: Optional[faiss.Index] = None
        self.commits: List[Dict] = []
        self.timings: Dict[str, float] = {}

    # ---------- file locations ----------
    @property
    def _index_path(self) -> Path:
        return self.index_dir / f"{self.name}_{self.index_type}.faiss"

    @property
    def _meta_path(self) -> Path:
        return self.index_dir / f"{self.name}_commits.json"

    @property
    def _emb_path(self) -> Path:
        return self.index_dir / f"{self.name}_embeddings.npy"

    @property
    def _emb_keys_path(self) -> Path:
        return self.index_dir / f"{self.name}_embedding_keys.json"

    # ---------- embedding cache ----------
    def _embed_commits(self, commits: List[Dict], use_cache: bool) -> np.ndarray:
        """Embed every commit, only paying for ones we haven't embedded before.

        The cache key is (sha, hash of embedding_text), so if you change how
        embedding_text is built (e.g. allow more diff lines), those commits are
        automatically re-embedded.
        """
        keys = [f"{c['sha']}:{_text_hash(c['embedding_text'])}" for c in commits]

        cached: Dict[str, np.ndarray] = {}
        if use_cache and self._emb_path.exists() and self._emb_keys_path.exists():
            old_matrix = np.load(self._emb_path)
            with open(self._emb_keys_path, "r", encoding="utf-8") as f:
                old_keys = json.load(f)
            if len(old_keys) == len(old_matrix):
                cached = {k: old_matrix[i] for i, k in enumerate(old_keys)}

        missing = [i for i, k in enumerate(keys) if k not in cached]
        print(f"[faiss] {len(keys) - len(missing)} embeddings cached, {len(missing)} to embed")

        if missing:
            new_vecs = self.embed_fn([commits[i]["embedding_text"] for i in missing])
            for i, vec in zip(missing, new_vecs):
                cached[keys[i]] = np.asarray(vec, dtype="float32")

        matrix = np.stack([cached[k] for k in keys]).astype("float32")

        if use_cache:
            np.save(self._emb_path, matrix)
            with open(self._emb_keys_path, "w", encoding="utf-8") as f:
                json.dump(keys, f)
        return matrix

    # ---------- index construction ----------
    def _make_index(self, dim: int, n: int) -> faiss.Index:
        if self.index_type == "flat":
            # Exact brute-force search. Fine up to ~100k vectors.
            return faiss.IndexFlatIP(dim)
        if self.index_type == "hnsw":
            # Graph-based approximate search. 32 = neighbours per node.
            index = faiss.IndexHNSWFlat(dim, 32, faiss.METRIC_INNER_PRODUCT)
            index.hnsw.efConstruction = 80
            index.hnsw.efSearch = 64
            return index
        # ivf: cluster vectors into nlist cells, search only nprobe cells per query.
        nlist = max(1, int(np.sqrt(n)))
        quantizer = faiss.IndexFlatIP(dim)
        return faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)

    def build(self, commits: List[Dict], use_cache: bool = True, save: bool = True) -> None:
        """Embed commits and build the index. Replaces any existing index."""
        if not commits:
            raise ValueError("No commits to index")

        t0 = time.perf_counter()
        matrix = _normalize(self._embed_commits(commits, use_cache))
        t1 = time.perf_counter()

        self.index = self._make_index(matrix.shape[1], len(matrix))
        if self.index_type == "ivf":
            self.index.train(matrix)  # IVF must learn its clusters before adding
            self.index.nprobe = max(1, self.index.nlist // 8)
        self.index.add(matrix)
        t2 = time.perf_counter()

        self.commits = list(commits)
        self.timings["embed_s"] = t1 - t0
        self.timings["index_build_s"] = t2 - t1

        if save:
            self.save()

    # ---------- persistence ----------
    def save(self) -> None:
        faiss.write_index(self.index, str(self._index_path))
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(self.commits, f)

    def load(self) -> bool:
        """Load a saved index. Returns False if nothing has been saved yet."""
        if not (self._index_path.exists() and self._meta_path.exists()):
            return False
        self.index = faiss.read_index(str(self._index_path))
        with open(self._meta_path, "r", encoding="utf-8") as f:
            self.commits = json.load(f)
        if self.index.ntotal != len(self.commits):
            raise RuntimeError("Index and commit list are out of sync; rebuild with use_cache=False")
        return True

    # ---------- search ----------
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Return the k commits most similar to `query`, best first.

        Each result is the commit dict plus "score" (cosine similarity, higher is better)
        and "rank" (1-based).
        """
        if self.index is None:
            raise RuntimeError("No index. Call build() or load() first.")

        t0 = time.perf_counter()
        q = _normalize(np.asarray(self.embed_fn([query]), dtype="float32"))
        t1 = time.perf_counter()
        scores, ids = self.index.search(q, min(k, self.index.ntotal))
        t2 = time.perf_counter()
        self.timings["query_embed_s"] = t1 - t0
        self.timings["query_search_s"] = t2 - t1

        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:  # approximate indexes pad with -1 when they find fewer than k
                continue
            commit = dict(self.commits[idx])
            commit["score"] = float(score)
            commit["rank"] = len(results) + 1
            results.append(commit)
        return results

    @staticmethod
    def format_for_llm(results: List[Dict], max_chars_each: int = 1500) -> str:
        """Turn search results into a context block to paste into an LLM prompt."""
        blocks = []
        for r in results:
            text = r["embedding_text"][:max_chars_each]
            blocks.append(f"[Result {r['rank']} | similarity {r['score']:.3f}]\n{text}")
        return "\n\n".join(blocks)
