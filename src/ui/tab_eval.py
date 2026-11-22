import json
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import streamlit as st

from evaluation.rescore import parse_judge_json, rescore
from llm_api.llm_client import LLMClient

GT_DIR = Path("tests/test_ground_truth")
EVAL_PROMPT_PATH = Path("src/llm_api/evaluator_prompt.md")


def discover_ground_truth_files() -> List[Path]:
    if not GT_DIR.exists():
        return []
    return sorted(list(GT_DIR.glob("*.md")))


def render_eval_tab(config: Dict[str, Any]):
    st.header("⚖️ Evaluation & Benchmark")
    st.markdown(
        "Evaluate a generated release summary against a ground truth document using an LLM judge "
        "and deterministic re-scoring (measuring Recall, Precision, and F1)."
    )

    openai_key = config.get("openai_key", "").strip()
    if not openai_key:
        st.warning("⚠️ **OpenAI API Key is missing.** Please enter your OpenAI API key in the sidebar under 🔑 API Credentials to run the evaluator.")

    # 1. Summary Selection
    st.subheader("1. Summary to Evaluate")
    existing_summary = st.session_state.get("generated_summary", "")

    summary_text = st.text_area(
        "Release Summary",
        value=existing_summary,
        height=180,
        placeholder="Paste a release summary here or generate one in Tab 3...",
        help="Defaults to the summary generated in Tab 3.",
    )

    # 2. Ground Truth Selection
    st.subheader("2. Ground Truth Reference")
    gt_files = discover_ground_truth_files()

    source_options = ["Upload .md file", "Paste text"]
    if gt_files:
        source_options.insert(0, "Choose from existing test files")

    gt_source = st.radio("Ground Truth Source", options=source_options, horizontal=True)
    ground_truth_text = ""

    if gt_source == "Choose from existing test files":
        file_map = {f.name: f for f in gt_files}
        picked_file_name = st.selectbox("Select Ground Truth File", options=list(file_map.keys()))
        if picked_file_name:
            ground_truth_text = file_map[picked_file_name].read_text(encoding="utf-8")
    elif gt_source == "Upload .md file":
        uploaded = st.file_uploader("Upload Ground Truth (.md or .txt)", type=["md", "txt"])
        if uploaded:
            ground_truth_text = uploaded.read().decode("utf-8")
    else:
        ground_truth_text = st.text_area("Paste Ground Truth Markdown", height=150, placeholder="Paste reference milestones here...")

    if ground_truth_text:
        with st.expander("Preview Ground Truth Content", expanded=False):
            st.markdown(ground_truth_text)

    st.divider()

    # 3. Execution
    run_btn = st.button(
        "⚖️ Run LLM Evaluation & Rescore",
        type="primary",
        disabled=not (bool(openai_key) and bool(summary_text.strip()) and bool(ground_truth_text.strip())),
        use_container_width=True,
    )

    if run_btn:
        with st.spinner("Running LLM judge and re-scoring audit..."):
            try:
                judge = LLMClient(api_key=openai_key, generation_model="gpt-4o-mini", prompt_file=EVAL_PROMPT_PATH)
                judge_prompt = f"Ground Truth: {ground_truth_text} \n\nGenerated Summary: {summary_text}"
                raw_response = judge.generate_content(judge_prompt)

                audit = parse_judge_json(raw_response)
                scores = rescore(audit)

                st.session_state["eval_audit"] = audit
                st.session_state["eval_scores"] = scores
                st.success("Evaluation completed!")
            except Exception as e:
                st.error(f"Evaluation failed: {e}")

    # 4. Display Results
    scores: Dict[str, Any] = st.session_state.get("eval_scores", None)
    audit: Dict[str, Any] = st.session_state.get("eval_audit", None)

    if not scores or not audit:
        st.info("Select ground truth and click **'⚖️ Run LLM Evaluation & Rescore'** above to generate scores.")
        return

    st.subheader("📊 Evaluation Scorecard")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("F1 Score", f"{scores.get('f1', 0.0):.3f}")
    m2.metric("Recall", f"{scores.get('recall', 0.0):.3f}")
    m3.metric("Precision", f"{scores.get('precision', 0.0):.3f}")
    m4.metric(
        "Milestones Covered",
        f"{scores.get('covered', 0)} / {scores.get('total_gt_milestones', 0)}",
        help=f"Partially covered: {scores.get('partially_covered', 0)}",
    )
    m5.metric(
        "Verified Claims",
        f"{scores.get('matched_claims', 0)} / {scores.get('total_claims', 0)}",
    )

    # 5. Detailed Breakdown Tabs
    sub_tab1, sub_tab2, sub_tab3 = st.tabs([
        "🎯 Milestone Recall Audit",
        "🔍 Narrative Precision Audit",
        "📄 Raw Judge Output",
    ])

    with sub_tab1:
        recall_items = audit.get("ground_truth_recall_audit", [])
        if recall_items:
            recall_rows = []
            for item in recall_items:
                recall_rows.append({
                    "Milestone": item.get("milestone", ""),
                    "Status": item.get("status", ""),
                    "Evidence": item.get("evidence", ""),
                })
            st.dataframe(pd.DataFrame(recall_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No milestone recall items found in audit.")

    with sub_tab2:
        claims = audit.get("narrative_precision_audit", [])
        if claims:
            claim_rows = []
            for c in claims:
                claim_rows.append({
                    "Claim": c.get("claim", ""),
                    "Matches Ground Truth": "✅ Yes" if c.get("matches_ground_truth") else "❌ No",
                    "Matched Milestone": c.get("matched_milestone", ""),
                })
            st.dataframe(pd.DataFrame(claim_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No narrative precision claims found in audit.")

    with sub_tab3:
        st.json(audit)
