from typing import Dict, Any, List
import pandas as pd
import streamlit as st
from filtering.noise_filter import filter_commits


def render_commits_tab(config: Dict[str, Any]):
    st.header("📦 Commit Selection & Noise Pre-Filtering")
    st.markdown(
        "Inspect repository commit history, select a release range, and review how rule-based filtering "
        "drops noise (merges, version bumps, assets, trivial fixes) before semantic embedding."
    )

    all_shas: List[str] = st.session_state.get("all_shas", [])
    github_api = st.session_state.get("github_api", None)

    if not all_shas or not github_api:
        st.info("👈 Select a repository in the sidebar and click **'Load / Refresh Commits'** to begin.")
        return

    st.success(f"Loaded **{len(all_shas):,}** total commits for **{config['owner']}/{config['repo']}**")

    # Select commit range (Newest and Oldest)
    col1, col2 = st.columns(2)

    curr_newest = st.session_state.get("selected_newest_sha", all_shas[0])
    curr_oldest = st.session_state.get("selected_oldest_sha", all_shas[-1])

    if curr_newest not in all_shas:
        curr_newest = all_shas[0]
    if curr_oldest not in all_shas:
        curr_oldest = all_shas[-1]

    newest_idx_default = all_shas.index(curr_newest)
    oldest_idx_default = all_shas.index(curr_oldest)

    with col1:
        st.markdown("**1. Select Newest Commit (End of Range)**")
        selected_newest = st.selectbox(
            "Newest Commit",
            options=all_shas,
            index=newest_idx_default,
            format_func=lambda s: f"{s[:7]} (index {all_shas.index(s)})",
            key="select_newest",
        )
    with col2:
        st.markdown("**2. Select Oldest Commit (Start of Range)**")
        selected_oldest = st.selectbox(
            "Oldest Commit",
            options=all_shas,
            index=oldest_idx_default,
            format_func=lambda s: f"{s[:7]} (index {all_shas.index(s)})",
            key="select_oldest",
        )

    st.session_state["selected_newest_sha"] = selected_newest
    st.session_state["selected_oldest_sha"] = selected_oldest

    start_idx = all_shas.index(selected_newest)
    end_idx = all_shas.index(selected_oldest)

    if start_idx > end_idx:
        st.error("⚠️ The newest commit must appear before or at the oldest commit in git log order.")
        return

    range_shas = all_shas[start_idx : end_idx + 1]
    st.session_state["range_shas"] = range_shas

    # Fetch raw commits for range
    with st.spinner(f"Loading {len(range_shas)} commits in selected range..."):
        raw_commits = [github_api.get_commit(sha, use_cache=True) for sha in range_shas]
        st.session_state["raw_commits"] = raw_commits

    # Filter Commits
    first_sha, last_sha = range_shas[-1], range_shas[0]
    if config["use_filter"]:
        kept, dropped = filter_commits(raw_commits, keep_shas=(first_sha, last_sha))
    else:
        kept = raw_commits
        dropped = []

    st.session_state["kept_commits"] = kept
    st.session_state["dropped_commits"] = dropped
    st.session_state["kept_shas"] = [c["sha"] for c in kept]

    # Display Metrics
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total in Range", f"{len(range_shas)}")
    m2.metric("Kept Commits (Signals)", f"{len(kept)}")
    m3.metric("Dropped Commits (Noise)", f"{len(dropped)}")
    reduction = (len(dropped) / len(range_shas) * 100) if range_shas else 0
    m4.metric("Noise Reduction", f"{reduction:.1f}%")

    # Detailed Tables
    sub_tab1, sub_tab2 = st.tabs([f"✅ Kept Commits ({len(kept)})", f"🚫 Dropped Commits ({len(dropped)})"])

    with sub_tab1:
        kept_rows = []
        for c in kept:
            sha = c["sha"][:7]
            commit_info = c.get("commit", {})
            author = commit_info.get("author", {}).get("name", "Unknown")
            date = commit_info.get("author", {}).get("date", "")[:10]
            msg = commit_info.get("message", "").splitlines()[0] if commit_info.get("message") else ""
            files_count = len(c.get("files", []))
            kept_rows.append({
                "SHA": sha,
                "Date": date,
                "Author": author,
                "Files": files_count,
                "Message": msg,
            })
        df_kept = pd.DataFrame(kept_rows)
        st.dataframe(df_kept, use_container_width=True, hide_index=True)

        with st.expander("🔍 Inspect Full Diff for a Kept Commit"):
            commit_shas_map = {f"{c['sha'][:7]} - {c.get('commit',{}).get('message','').splitlines()[0][:50]}": c for c in kept}
            picked = st.selectbox("Pick Commit", options=list(commit_shas_map.keys()))
            if picked:
                raw_picked = commit_shas_map[picked]
                parsed = github_api.parse_commit(raw_picked, use_cache=True)
                st.code(parsed.get("llm_summary", ""), language="markdown")

    with sub_tab2:
        if not dropped:
            st.info("No commits were dropped (Noise filtering is disabled or all commits passed).")
        else:
            dropped_rows = []
            for d in dropped:
                dropped_rows.append({
                    "SHA": d["sha"],
                    "Reason": d["reason"],
                    "Message": d["message"],
                })
            df_dropped = pd.DataFrame(dropped_rows)
            st.dataframe(df_dropped, use_container_width=True, hide_index=True)

            # Show distribution of drop reasons
            st.markdown("**Drop Reasons Breakdown:**")
            reason_counts = df_dropped["Reason"].value_counts()
            st.bar_chart(reason_counts)
