from pathlib import Path
from typing import Dict, Any, List
import streamlit as st

from llm_api.llm_client import LLMClient
from pipeline.cp4_pipeline import CP4Pipeline, RetrievalConfig


def get_prompt_path(prompt_name: str) -> Path:
    nested = Path("src/llm_api/prompts") / prompt_name
    if nested.exists():
        return nested
    top = Path("src/llm_api") / prompt_name
    if top.exists():
        return top
    return Path("src/llm_api/analyzer_prompt.md")


def render_summary_tab(config: Dict[str, Any]):
    st.header("📝 Release Summary Generation")
    st.markdown(
        "Assemble the retrieved commits into an LLM context and generate structured, human-readable "
        "release notes using OpenAI."
    )

    pipe: CP4Pipeline = st.session_state.get("cp4_pipeline", None)
    retrieved_shas: List[str] = st.session_state.get("retrieved_shas", None)
    retrieval_cfg: RetrievalConfig = st.session_state.get("retrieval_config", None)
    openai_key = config.get("openai_key", "").strip()

    if not pipe or not retrieved_shas or not retrieval_cfg:
        st.info("👈 Please build the vector index and retrieve commits in **Tab 2: 🔍 Retrieval** first.")
        return

    # 1. Check API Key
    if not openai_key:
        st.warning("⚠️ **OpenAI API Key is missing.** Please enter your OpenAI API key in the sidebar under 🔑 API Credentials.")

    # 2. Build and preview context
    prompt_path = get_prompt_path(config.get("prompt_name", "analyzer_prompt.md"))
    context = pipe.build_context(retrieval_cfg, retrieved_shas)

    st.markdown("### 📋 Context Assembly Preview")

    c1, c2, c3 = st.columns(3)
    c1.metric("Commits in Context", f"{len(retrieved_shas)}")
    c2.metric("Context Size", f"{len(context):,} chars")
    c3.metric("System Prompt", prompt_path.name)

    if retrieval_cfg.force_include:
        st.caption("ℹ️ *Forced inclusion active: bookend commits (first & last) and repository README are included in this context.*")

    with st.expander("🔍 Inspect Full Prompt Context sent to LLM", expanded=False):
        st.caption("This exact text block is passed to the LLM's user message:")
        st.text_area("LLM Context", value=context, height=250, disabled=True)

    with st.expander(f"📄 View System Prompt Template (`{prompt_path.name}`)", expanded=False):
        if prompt_path.exists():
            st.code(prompt_path.read_text(encoding="utf-8"), language="markdown")

    st.divider()

    # 3. Model Selection & Generation
    col_model, col_gen = st.columns([1, 2])
    with col_model:
        model_choice = st.selectbox(
            "OpenAI Model",
            options=["gpt-4o-mini", "gpt-4o"],
            index=0,
            help="gpt-4o-mini is fast and costs only fractions of a cent per run.",
        )
    with col_gen:
        st.write("")
        st.write("")
        generate_btn = st.button("✨ Generate Release Summary with LLM", type="primary", use_container_width=True, disabled=not bool(openai_key))

    if generate_btn:
        with st.spinner(f"Generating summary with {model_choice}..."):
            try:
                llm = LLMClient(api_key=openai_key, generation_model=model_choice, prompt_file=prompt_path)
                response = llm.generate_content(context)
                st.session_state["generated_summary"] = response
                st.session_state["summary_model"] = model_choice
                st.session_state["summary_prompt"] = prompt_path.name
                st.success("Summary generated successfully!")
            except Exception as e:
                st.error(f"Failed to generate summary: {e}")

    # 4. Display & Export Output
    generated_summary = st.session_state.get("generated_summary", None)
    if generated_summary:
        st.subheader("📜 Generated Release Notes")

        word_count = len(generated_summary.split())
        st.caption(f"Generated with **{st.session_state.get('summary_model', model_choice)}** using `{st.session_state.get('summary_prompt', prompt_path.name)}` • **{word_count} words**")

        st.markdown(generated_summary)

        st.divider()
        col_dl, col_raw = st.columns([1, 3])
        with col_dl:
            repo_name = config.get("repo", "repo")
            end_sha = pipe.first_sha[:7] if hasattr(pipe, "first_sha") else "release"
            st.download_button(
                label="⬇️ Download Summary (.md)",
                data=generated_summary,
                file_name=f"release_summary_{repo_name}_{end_sha}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_raw:
            with st.expander("View Raw Markdown Source"):
                st.code(generated_summary, language="markdown")
