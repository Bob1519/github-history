import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path("github_cache")


def discover_cached_repos() -> List[str]:
    """Scan github_cache/ for any *_shas.json files (both full and partial lists).

    Cache files are keyed by repo name only, so the owner comes from _repo_owners.json
    (written by GitHubAPI); repos cached before that file existed fall back to repo/repo.
    """
    if not CACHE_DIR.exists():
        return []
    owners = {}
    registry = CACHE_DIR / "_repo_owners.json"
    if registry.exists():
        try:
            owners = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            owners = {}
    cached = set()
    # Matches both repo_all_shas.json and repo_100_shas.json
    for p in CACHE_DIR.glob("*_shas.json"):
        repo_name = re.sub(r"_(all|\d+)_shas\.json$", "", p.name)
        cached.add(f"{owners.get(repo_name, repo_name)}/{repo_name}")
    return sorted(list(cached))


def render_sidebar() -> Dict[str, Any]:
    st.sidebar.title("📜 GitHub History")
    st.sidebar.caption("Semantic RAG Release Notes & History Explorer")

    # 1. API Credentials
    with st.sidebar.expander("🔑 API Credentials", expanded=False):
        github_token = st.text_input(
            "GitHub API Token",
            value=os.getenv("GITHUB_API_KEY", ""),
            type="password",
            help="Personal Access Token for GitHub API (avoids 60 req/hr rate limit)",
        )
        openai_key = st.text_input(
            "OpenAI API Key",
            value=os.getenv("OPENAI_API_KEY", ""),
            type="password",
            help="API Key for LLM summarization and evaluation (gpt-4o-mini)",
        )

    # 2. Repository Selector
    st.sidebar.subheader("📁 Repository")
    cached_repos = discover_cached_repos()

    owner = "tqdm"
    repo = "tqdm"

    if cached_repos:
        repo_mode = st.sidebar.radio(
            "Source",
            options=["Cached Repos", "Custom Repo"],
            horizontal=True,
        )
        if repo_mode == "Cached Repos":
            selected_cached = st.sidebar.selectbox("Select Cached Repository", options=cached_repos)
            if "/" in selected_cached:
                owner, repo = selected_cached.split("/", 1)
            else:
                owner, repo = selected_cached, selected_cached
        else:
            custom_input = st.sidebar.text_input(
                "GitHub Repo URL or owner/repo",
                value="tqdm/tqdm",
                placeholder="e.g. psf/requests or https://github.com/psf/requests",
            )
            cleaned = re.sub(r"^https?://github\.com/", "", custom_input.strip()).strip("/")
            if "/" in cleaned:
                parts = cleaned.split("/")
                owner, repo = parts[0], parts[1]
            else:
                owner, repo = cleaned, cleaned
    else:
        st.sidebar.caption("*(No cached repositories found in github_cache/)*")
        custom_input = st.sidebar.text_input(
            "GitHub Repo URL or owner/repo",
            value="tqdm/tqdm",
            placeholder="e.g. psf/requests or https://github.com/psf/requests",
        )
        cleaned = re.sub(r"^https?://github\.com/", "", custom_input.strip()).strip("/")
        if "/" in cleaned:
            parts = cleaned.split("/")
            owner, repo = parts[0], parts[1]
        else:
            owner, repo = cleaned, cleaned

    max_commits_opt = st.sidebar.selectbox(
        "Max Commits to Fetch",
        options=[100, 250, 500, "All"],
        index=3,
        help="Limit number of commits to pull from GitHub if not fully cached.",
    )
    max_commits = None if max_commits_opt == "All" else int(max_commits_opt)

    load_btn = st.sidebar.button("🔄 Load / Refresh Commits", type="primary", use_container_width=True)

    # 3. RAG Pipeline Knobs
    st.sidebar.subheader("⚙️ Pipeline Configuration")
    chunking = st.sidebar.radio(
        "Chunking Strategy",
        options=["per_commit", "per_file"],
        index=0,
        help="'per_commit' indexes one summary vector per commit. 'per_file' indexes diff chunks for each changed file.",
    )
    use_filter = st.sidebar.checkbox(
        "Noise Filtering",
        value=True,
        help="Exclude merge commits, version bumps, assets, and trivial changes before embedding.",
    )
    force_include = st.sidebar.checkbox(
        "Forced Inclusion",
        value=True,
        help="Always include the first/last commits and the README in the LLM context.",
    )

    query_mode = st.sidebar.selectbox(
        "Retrieval Queries",
        options=["CP4 5-Theme Multi-Queries", "CP3 Single Query", "Custom Query"],
        index=0,
    )
    custom_query = ""
    if query_mode == "Custom Query":
        custom_query = st.sidebar.text_area("Enter Custom Search Query", value="New public features and major bug fixes")

    top_k = st.sidebar.slider("Top-k Commits per Query", min_value=1, max_value=15, value=5)

    prompt_name = st.sidebar.selectbox(
        "Prompt Template",
        options=["analyzer_prompt.md", "concise_prompt.md", "structured_prompt.md"],
        index=0,
    )

    st.sidebar.divider()
    run_all_btn = st.sidebar.button(
        "⚡ Run Full Pipeline (End-to-End)",
        type="primary",
        use_container_width=True,
        help="Runs everything in one click: fetch commits -> filter noise -> build FAISS index -> retrieve commits -> generate release summary in Tab 3.",
    )

    return {
        "github_token": github_token,
        "openai_key": openai_key,
        "owner": owner,
        "repo": repo,
        "max_commits": max_commits,
        "load_btn": load_btn,
        "run_all_btn": run_all_btn,
        "chunking": chunking,
        "use_filter": use_filter,
        "force_include": force_include,
        "query_mode": query_mode,
        "custom_query": custom_query,
        "top_k": top_k,
        "prompt_name": prompt_name,
    }
