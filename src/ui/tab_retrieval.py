from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import streamlit as st

from pipeline.cp4_pipeline import (
    CP4Pipeline,
    RetrievalConfig,
    CP3_QUERY,
    MULTI_QUERIES,
)


@st.cache_resource
def load_embedder(model_name: str = "bge-m3"):
    """Load and cache the embedding function across Streamlit reruns."""
    if model_name == "bge-m3":
        from sentence_transformers import SentenceTransformer
        try:
            model = SentenceTransformer("BAAI/bge-m3", local_files_only=True)
        except Exception:  # not downloaded yet: fetch it once (~2.3 GB) into the Hugging Face cache
            model = SentenceTransformer("BAAI/bge-m3")
        return lambda texts: model.encode(texts, batch_size=8, show_progress_bar=len(texts) > 50).tolist()
    elif model_name == "hashing":
        from sklearn.feature_extraction.text import HashingVectorizer
        vec = HashingVectorizer(n_features=4096, alternate_sign=False, ngram_range=(1, 2), stop_words="english")
        return lambda texts: vec.transform(texts).toarray().tolist()
    raise ValueError(f"Unknown embedder: {model_name}")


def get_queries(config: Dict[str, Any]) -> List[str]:
    mode = config.get("query_mode", "CP4 5-Theme Multi-Queries")
    if mode == "CP4 5-Theme Multi-Queries":
        return MULTI_QUERIES
    elif mode == "CP3 Single Query":
        return [CP3_QUERY]
    elif mode == "Custom Query":
        custom = config.get("custom_query", "").strip()
        return [custom] if custom else [CP3_QUERY]
    return MULTI_QUERIES


def get_prompt_path(prompt_name: str) -> Path:
    nested = Path("src/llm_api/prompts") / prompt_name
    if nested.exists():
        return nested
    top = Path("src/llm_api") / prompt_name
    if top.exists():
        return top
    return Path("src/llm_api/analyzer_prompt.md")


def render_retrieval_tab(config: Dict[str, Any]):
    st.header("🔍 Semantic Retrieval & Vector Store")
    st.markdown(
        "Build or load a FAISS vector index over your selected commits and run semantic similarity "
        "search to retrieve the most release-relevant changes."
    )

    github_api = st.session_state.get("github_api", None)
    range_shas: List[str] = st.session_state.get("range_shas", [])
    newest_sha = st.session_state.get("selected_newest_sha", None)
    oldest_sha = st.session_state.get("selected_oldest_sha", None)

    if not github_api or not range_shas or not newest_sha or not oldest_sha:
        st.info("👈 Please load a repository and select a commit range in **Tab 1: 📦 Commits** first.")
        return

    # 1. Active Repo & Range Status Banner
    kept_count = len(st.session_state.get("kept_commits", range_shas))
    dropped_count = len(st.session_state.get("dropped_commits", []))
    filter_status = (
        f"{kept_count} indexed after noise filter ({dropped_count} dropped out of {len(range_shas)} total)"
        if config["use_filter"]
        else f"{len(range_shas)} commits in range (filter off)"
    )
    st.info(
        f"📂 **Active Repository:** `{config['owner']}/{config['repo']}` | "
        f"**Selected Range:** `{newest_sha[:7]}` (newest) → `{oldest_sha[:7]}` (oldest) — **{filter_status}**"
    )

    # 2. Pipeline Settings Breakdown
    st.markdown("### ⚙️ Pipeline Settings")
    queries = get_queries(config)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**FAISS Index Structure**")
        filter_label = "Kept commits only" if config["use_filter"] else "All commits in range"
        st.caption(f"• Chunking: `{config['chunking']}`\n• Scope: `{filter_label}`")
    with c2:
        st.markdown("**Vector Search Settings**")
        st.caption(f"• Queries: `{len(queries)} query/queries`\n• Top-k: `{config['top_k']} commits/query`")
    with c3:
        st.markdown("**Post-Retrieval Context Rule**")
        force_desc = "Append bookend commits (first & last) + README" if config["force_include"] else "Disabled (vector search results only)"
        st.caption(f"• Forced Inclusion: `{force_desc}`")

    with st.expander("View Active Search Queries", expanded=False):
        for i, q in enumerate(queries, 1):
            st.markdown(f"{i}. *\"{q}\"*")

    st.divider()

    # 2. Embedder Selection & Action Button
    col_embed, col_btn = st.columns([1, 2])
    with col_embed:
        embedder_choice = st.selectbox(
            "Embedding Model",
            options=["bge-m3", "hashing"],
            index=0,
            help="'bge-m3' is the dense semantic model. 'hashing' is an offline fast test embedder.",
        )
    with col_btn:
        st.write("")
        st.write("")
        run_retrieval_btn = st.button("🚀 Build FAISS Index & Retrieve Commits", type="primary", use_container_width=True)

    # 3. Execution
    if run_retrieval_btn:
        with st.spinner("Initializing embedder and building FAISS vector store..."):
            try:
                embed_fn = load_embedder(embedder_choice)
                pipe = CP4Pipeline(
                    github=github_api,
                    embed_fn=embed_fn,
                    newest_sha=newest_sha,
                    oldest_sha=oldest_sha,
                    embedder_name=embedder_choice,
                )
                retrieval_cfg = RetrievalConfig(
                    name="ui_retrieval",
                    chunking=config["chunking"],
                    use_filter=config["use_filter"],
                    force_include=config["force_include"],
                    queries=queries,
                    k=config["top_k"],
                    prompt_file=get_prompt_path(config["prompt_name"]),
                )

                retrieved_shas = pipe.retrieve(retrieval_cfg)
                st.session_state["cp4_pipeline"] = pipe
                st.session_state["retrieval_config"] = retrieval_cfg
                st.session_state["retrieved_shas"] = retrieved_shas
                st.success(f"Retrieved **{len(retrieved_shas)}** release-worthy commits across {len(queries)} queries!")
            except Exception as e:
                st.error(f"Error building vector store or retrieving commits: {e}")

    retrieved_shas = st.session_state.get("retrieved_shas", None)
    pipe: CP4Pipeline = st.session_state.get("cp4_pipeline", None)
    retrieval_cfg: RetrievalConfig = st.session_state.get("retrieval_config", None)

    if not retrieved_shas or not pipe or not retrieval_cfg:
        st.info("Click **'🚀 Build FAISS Index & Retrieve Commits'** above to run vector retrieval.")
        return

    # 4. Retrieval Metrics & Table
    eligible_shas = pipe.shas_for(retrieval_cfg)
    m1, m2, m3 = st.columns(3)
    drop_info = f"-{len(pipe.dropped)} noise dropped" if retrieval_cfg.use_filter else "filter disabled"
    m1.metric("Indexed Candidate Commits", f"{len(eligible_shas)}", delta=drop_info, delta_color="off")
    m2.metric("Retrieved Commits (Top-k)", f"{len(retrieved_shas)}")
    pct = (len(retrieved_shas) / len(eligible_shas) * 100) if eligible_shas else 0
    m3.metric("Retrieval Ratio (Retrieved / Indexed)", f"{pct:.1f}%")

    st.subheader(f"📋 Retrieved Commits ({len(retrieved_shas)} in Chronological Order)")
    st.caption("These commits will be formatted into the context fed to the LLM for summarization.")

    retrieved_rows = []
    for sha in retrieved_shas:
        p = pipe.parsed.get(sha, {})
        retrieved_rows.append({
            "SHA": sha[:7],
            "Date": p.get("date", "")[:10],
            "Author": p.get("author", "Unknown"),
            "Files": len(p.get("files", [])),
            "Message": p.get("message", "").splitlines()[0] if p.get("message") else "",
        })
    df_retrieved = pd.DataFrame(retrieved_rows)
    st.dataframe(df_retrieved, use_container_width=True, hide_index=True)

    with st.expander("🔍 Inspect Diff of a Retrieved Commit"):
        picked_sha = st.selectbox(
            "Select Retrieved Commit",
            options=retrieved_shas,
            format_func=lambda s: f"{s[:7]} - {pipe.parsed.get(s, {}).get('message', '').splitlines()[0][:50]}",
        )
        if picked_sha:
            parsed = pipe.parsed.get(picked_sha, {})
            st.code(parsed.get("llm_summary", ""), language="markdown")

    # 5. Ad-hoc Search Playground
    st.divider()
    st.subheader("🧪 Ad-Hoc Vector Search Playground")
    st.markdown("Test any arbitrary query against this vector store to see how similarity ranking works:")

    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        test_query = st.text_input(
            "Search Query",
            value="bug fixes or edge case handling",
            placeholder="Type a feature, bug, or keyword...",
        )
    with search_col2:
        test_k = st.number_input("Top-k Results", min_value=1, max_value=20, value=5)

    if st.button("🔎 Run Test Query"):
        with st.spinner("Searching FAISS index..."):
            try:
                store = pipe.store_for(retrieval_cfg)
                hits = store.search(test_query, k=test_k)
                if not hits:
                    st.warning("No matches found.")
                else:
                    hit_rows = []
                    for h in hits:
                        sha = h.get("commit_sha", h.get("sha", ""))
                        p = pipe.parsed.get(sha, {})
                        chunk_id = h.get("sha", "")
                        matched_file = (
                            chunk_id.split(":", 1)[1]
                            if ":" in chunk_id and not chunk_id.endswith(":_message")
                            else "Full Commit"
                        )
                        hit_rows.append({
                            "Score": f"{h.get('score', 0.0):.4f}",
                            "SHA": sha[:7],
                            "Date": p.get("date", "")[:10],
                            "Author": p.get("author", "Unknown"),
                            "Matched Target": matched_file,
                            "Message": p.get("message", "").splitlines()[0] if p.get("message") else "",
                        })
                    st.dataframe(pd.DataFrame(hit_rows), use_container_width=True, hide_index=True)

                    with st.expander("🔍 Inspect Diff of a Search Hit"):
                        hit_options = {
                            f"[{h.get('score', 0.0):.4f}] {h.get('commit_sha', h.get('sha', ''))[:7]} - {pipe.parsed.get(h.get('commit_sha', h.get('sha', '')), {}).get('message', '').splitlines()[0][:50]}": h
                            for h in hits
                        }
                        picked_hit_label = st.selectbox("Pick Matching Hit", options=list(hit_options.keys()))
                        if picked_hit_label:
                            picked_h = hit_options[picked_hit_label]
                            picked_sha = picked_h.get("commit_sha", picked_h.get("sha", ""))
                            parsed_hit = pipe.parsed.get(picked_sha, {})
                            st.code(parsed_hit.get("llm_summary", ""), language="markdown")
            except Exception as e:
                st.error(f"Search failed: {e}")
