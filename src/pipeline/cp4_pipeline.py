"""Checkpoint 4 pipeline: configurable chunking, noise filtering, forced inclusion, multi-query retrieval.

The CP3 Pipeline class is left unchanged so the CP3 test still reproduces. This class makes
every CP4 knob a field on RetrievalConfig so the benchmark scripts can compare them one at a time:

    chunking       "per_commit" (CP3) or "per_file"
    use_filter     drop noise commits (merges, version bumps, asset-only, trivial) before embedding
    force_include  always put the first + last commit of the range and the README into the LLM context
    queries / k    search queries and how many *commits* to keep per query (results are unioned)
    prompt_file    system prompt used for the summary
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List

from chunking.chunkers import per_commit_chunks, per_file_chunks
from filtering.noise_filter import filter_commits
from github_api.github_api import GitHubAPI
from vector_store.faiss_index import CommitVectorStore

CP3_QUERY = "Major Architectural features refactors milestones releases"

# Repo-agnostic themes: one query per kind of change a release history usually contains.
MULTI_QUERIES = [
    "new features, new parameters or options added to the public API",
    "bug fixes for incorrect behaviour or edge cases",
    "architecture refactor: moving code into new modules, classes or files",
    "testing, continuous integration and build tooling changes",
    "performance and efficiency improvements",
]

DEFAULT_PROMPT = Path("src/llm_api/analyzer_prompt.md")
MAX_CHARS_PER_COMMIT = 6000
README_MAX_CHARS = 4000


@dataclass
class RetrievalConfig:
    name: str
    chunking: str = "per_commit"
    use_filter: bool = False
    force_include: bool = False
    queries: List[str] = field(default_factory=lambda: [CP3_QUERY])
    k: int = 5
    prompt_file: Path = DEFAULT_PROMPT


class CP4Pipeline:
    def __init__(self, github: GitHubAPI, embed_fn: Callable, newest_sha: str, oldest_sha: str,
                 embedder_name: str = "bge-m3"):
        self.github = github
        self.embed_fn = embed_fn
        self.embedder_name = embedder_name
        self._stores: Dict[tuple, CommitVectorStore] = {}

        all_shas = github.fetch_all_commit_shas()
        start, end = all_shas.index(newest_sha), all_shas.index(oldest_sha)
        self.range_shas = all_shas[start:end + 1]                   # newest first, same as CP3 test
        self.raw = {s: github.get_commit(s) for s in self.range_shas}
        self.parsed = {s: github.parse_commit(self.raw[s]) for s in self.range_shas}
        self.position = {s: i for i, s in enumerate(self.range_shas)}
        self.first_sha, self.last_sha = self.range_shas[-1], self.range_shas[0]

        kept, self.dropped = filter_commits([self.raw[s] for s in self.range_shas],
                                            keep_shas=(self.first_sha, self.last_sha))
        self.kept_shas = [c["sha"] for c in kept]

    # ---------- indexing ----------
    def shas_for(self, config: RetrievalConfig) -> List[str]:
        return self.kept_shas if config.use_filter else self.range_shas

    def store_for(self, config: RetrievalConfig) -> CommitVectorStore:
        key = (config.chunking, config.use_filter)
        if key not in self._stores:
            shas = self.shas_for(config)
            if config.chunking == "per_commit":
                chunks = per_commit_chunks([self.parsed[s] for s in shas])
            elif config.chunking == "per_file":
                chunks = per_file_chunks([self.raw[s] for s in shas])
            else:
                raise ValueError(f"unknown chunking {config.chunking}")
            name = f"{self.github.repo}_cp4_{self.embedder_name}_{config.chunking}_{'filtered' if config.use_filter else 'all'}"
            store = CommitVectorStore(self.embed_fn, name=name, index_type="flat")
            store.build(chunks, use_cache=True, save=True)
            self._stores[key] = store
        return self._stores[key]

    # ---------- retrieval ----------
    def search_commits(self, config: RetrievalConfig, query: str, k: int) -> List[str]:
        """Top-k distinct commits for one query. Per-file chunks are collapsed to their commit
        (a commit's score is its best-matching file)."""
        store = self.store_for(config)
        hits = store.search(query, k=len(store.commits))  # small repos: rank everything, then dedupe
        seen, out = set(), []
        for h in hits:
            sha = h["commit_sha"]
            if sha not in seen:
                seen.add(sha)
                out.append(sha)
                if len(out) == k:
                    break
        return out

    def retrieve(self, config: RetrievalConfig) -> List[str]:
        selected = []
        for q in config.queries:
            for sha in self.search_commits(config, q, config.k):
                if sha not in selected:
                    selected.append(sha)
        if config.force_include:
            for sha in (self.first_sha, self.last_sha):
                if sha not in selected:
                    selected.append(sha)
        return sorted(selected, key=lambda s: -self.position[s])  # oldest -> newest

    # ---------- LLM ----------
    def build_context(self, config: RetrievalConfig, shas: List[str]) -> str:
        ctx = f"Repo: {self.github.repo} \nOwner: {self.github.owner}\n"
        if config.force_include:
            path, readme = self.github.get_readme_at_commit(self.last_sha)
            if readme:
                ctx += (f"\n=== {path} at the end of this range (reference only; describes the "
                        f"project, not individual changes) ===\n{readme[:README_MAX_CHARS]}\n=== end {path} ===\n")
        ctx += "\n=== Retrieved commits, oldest to newest ===\n"
        for sha in shas:
            ctx += "\n" + self.parsed[sha]["llm_summary"][:MAX_CHARS_PER_COMMIT]
        return ctx

    def summarize(self, config: RetrievalConfig, llm_key: str) -> Dict:
        from llm_api.llm_client import LLMClient  # imported here so retrieval-only runs need no OpenAI key
        shas = self.retrieve(config)
        context = self.build_context(config, shas)
        llm = LLMClient(llm_key, prompt_file=Path(config.prompt_file))
        response = llm.generate_content(context)
        return {"response": response, "retrieved_shas": [s[:7] for s in shas],
                "context_chars": len(context)}
