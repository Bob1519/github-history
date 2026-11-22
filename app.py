import sys
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv

# Ensure 'src' is discoverable on python path
ROOT = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

load_dotenv()

from github_api.github_api import GitHubAPI
from filtering.noise_filter import filter_commits
from pipeline.cp4_pipeline import CP4Pipeline, RetrievalConfig
from llm_api.llm_client import LLMClient
from ui.sidebar import render_sidebar
from ui.tab_commits import render_commits_tab
from ui.tab_retrieval import render_retrieval_tab, load_embedder, get_queries, get_prompt_path
from ui.tab_summary import render_summary_tab
from ui.tab_eval import render_eval_tab

# Page configuration
st.set_page_config(
    page_title="GitHub History Analyzer",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom header styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #666;
        margin-bottom: 1.5rem;
    }
    </style>
    <div class="main-title">📜 GitHub History & Release Notes Generator</div>
    <div class="sub-title">Semantic commit exploration, noise filtering, vector retrieval, and LLM summarization.</div>
    """,
    unsafe_allow_html=True,
)

# Render sidebar controls
config = render_sidebar()

# Session State Initialization
if "current_repo_key" not in st.session_state:
    st.session_state["current_repo_key"] = None
if "all_shas" not in st.session_state:
    st.session_state["all_shas"] = []
if "github_api" not in st.session_state:
    st.session_state["github_api"] = None

repo_key = f"{config['owner']}/{config['repo']}"

# Handle Fetch / Load Action
should_load = config["load_btn"] or (st.session_state["github_api"] is None and bool(config["owner"] and config["repo"]))

if should_load:
    # Clear previous widget selections so dropdowns snap to the full newly-loaded range
    for k in ("select_newest", "select_oldest", "selected_newest_sha", "selected_oldest_sha"):
        st.session_state.pop(k, None)

    with st.spinner(f"Fetching commit list for {repo_key}..."):
        try:
            api = GitHubAPI(
                owner=config["owner"],
                repo=config["repo"],
                github_api_key=config["github_token"] or None,
            )
            shas = api.fetch_all_commit_shas(max_commits=config["max_commits"], use_cache=True)
            st.session_state["github_api"] = api
            st.session_state["all_shas"] = shas
            st.session_state["current_repo_key"] = repo_key
        except Exception as e:
            st.error(f"Failed to fetch commits for {repo_key}: {e}")

# Handle Run Full Pipeline (End-to-End) Action
if config["run_all_btn"]:
    if not config["openai_key"]:
        st.sidebar.error("⚠️ Please enter an OpenAI API key to generate the summary.")
    else:
        with st.spinner("⚡ Running CP4Pipeline end-to-end..."):
            try:
                # 1. Ensure API and commits are loaded
                api = st.session_state.get("github_api")
                all_shas = st.session_state.get("all_shas", [])
                if not api or not all_shas or st.session_state.get("current_repo_key") != repo_key:
                    api = GitHubAPI(owner=config["owner"], repo=config["repo"], github_api_key=config["github_token"] or None)
                    all_shas = api.fetch_all_commit_shas(max_commits=config["max_commits"], use_cache=True)
                    st.session_state["github_api"] = api
                    st.session_state["all_shas"] = all_shas
                    st.session_state["current_repo_key"] = repo_key

                # 2. Initialize pipeline (CP4Pipeline handles commit fetching, parsing, and filtering internally)
                embed_fn = load_embedder("bge-m3")
                newest_sha = st.session_state.get("selected_newest_sha", all_shas[0])
                oldest_sha = st.session_state.get("selected_oldest_sha", all_shas[-1])
                pipe = CP4Pipeline(api, embed_fn, newest_sha, oldest_sha, embedder_name="bge-m3")

                # 3. Configure retrieval
                prompt_path = get_prompt_path(config["prompt_name"])
                retrieval_cfg = RetrievalConfig(
                    name="end_to_end",
                    chunking=config["chunking"],
                    use_filter=config["use_filter"],
                    force_include=config["force_include"],
                    queries=get_queries(config),
                    k=config["top_k"],
                    prompt_file=prompt_path,
                )

                # 4. Single call to summarize
                out = pipe.summarize(retrieval_cfg, llm_key=config["openai_key"])

                # 5. Store state so Tabs 1, 2, and 3 reflect the run
                st.session_state["cp4_pipeline"] = pipe
                st.session_state["retrieval_config"] = retrieval_cfg
                st.session_state["retrieved_shas"] = [s for s in pipe.retrieve(retrieval_cfg)]
                st.session_state["generated_summary"] = out["response"]
                st.session_state["summary_model"] = "gpt-4o-mini"
                st.session_state["summary_prompt"] = prompt_path.name

                st.session_state["range_shas"] = pipe.range_shas
                st.session_state["selected_newest_sha"] = newest_sha
                st.session_state["selected_oldest_sha"] = oldest_sha
                st.session_state["raw_commits"] = [pipe.raw[s] for s in pipe.range_shas]
                st.session_state["kept_commits"] = [pipe.raw[s] for s in pipe.kept_shas]
                st.session_state["dropped_commits"] = pipe.dropped
                st.session_state["kept_shas"] = pipe.kept_shas

                st.sidebar.success("✅ Full pipeline completed! Tabs 1, 2, and 3 are populated.")
            except Exception as e:
                st.sidebar.error(f"Pipeline failed: {e}")

# Define main application tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📦 1. Commits & Pre-Filtering",
    "🔍 2. Semantic Retrieval",
    "📝 3. Release Summary",
    "⚖️ 4. Evaluation & Benchmark",
])

with tab1:
    render_commits_tab(config)

with tab2:
    render_retrieval_tab(config)

with tab3:
    render_summary_tab(config)

with tab4:
    render_eval_tab(config)
