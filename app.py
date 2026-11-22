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
from ui.sidebar import render_sidebar
from ui.tab_commits import render_commits_tab
from ui.tab_retrieval import render_retrieval_tab
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
