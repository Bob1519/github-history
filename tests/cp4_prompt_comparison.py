"""Checkpoint 4, experiment 2: end-to-end comparison of retrieval settings and LLM prompts.

Uses OpenAI (gpt-4o-mini, a few cents total). Run from the repo root AFTER the retrieval benchmark:
    python tests/cp4_prompt_comparison.py                 # 2 repeats per config
    python tests/cp4_prompt_comparison.py --repeats 1     # faster

Configs:
    A cp3_baseline       CP3 settings: per-commit, no filter, 1 query, k=5, original prompt
    B cp4_retrieval      filter + forced first/last/README + 5 themed queries, original prompt
    C cp4_concise        B + concise prompt (<= 350 words, release-worthy only)
    D cp4_structured     B + structured sectioned prompt (bullets, max 5 per section)

Each generated summary is judged by the CP3 evaluator prompt against the corrected (in-range)
ground truth, then re-scored deterministically (src/evaluation/rescore.py).
Outputs in tests/test_output/cp4/: <config>_run<i>.md, <config>_run<i>_eval.json, prompt_results.{json,md}
"""
import argparse
import json
import os
import statistics
from pathlib import Path

from cp4_common import NEWEST_SHA, OLDEST_SHA, OUT_DIR, ROOT, make_embedder
from dotenv import load_dotenv
from evaluation.rescore import parse_judge_json, rescore
from github_api.github_api import GitHubAPI
from llm_api.llm_client import LLMClient
from pipeline.cp4_pipeline import CP3_QUERY, MULTI_QUERIES, CP4Pipeline, RetrievalConfig

GROUND_TRUTH = Path("tests/test_ground_truth/tqdm_200_314_ground_truth_inrange.md")
PROMPTS = Path("src/llm_api/prompts")


def pick_chunking() -> str:
    """Winner = filtered variant whose multi-query context covers the most milestones;
    ties broken by milestone-retrieval MRR (Part A)."""
    path = OUT_DIR / "retrieval_results.json"
    if not path.exists():
        print("[auto] no retrieval_results.json yet -> using per_commit")
        return "per_commit"
    r = json.load(open(path))
    def key(c):
        b = r["part_b_pipeline_coverage"][f"{c}+filter | cp4_multi_query"]
        return (b["milestones_covered"], r["part_a_milestone_retrieval"][f"{c}+filter"]["summary"]["mrr"])
    best = max(["per_commit", "per_file"], key=key)
    print(f"[auto] chunking for B-D: {best} (coverage, MRR) = {key(best)}")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--chunking", default="auto", choices=["auto", "per_commit", "per_file"],
                    help="chunking for configs B-D; 'auto' picks the winner from cp4_retrieval_benchmark.py")
    ap.add_argument("--embedder", default="bge-m3", choices=["bge-m3", "hashing"])
    args = ap.parse_args()
    load_dotenv()
    os.chdir(ROOT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    llm_key = os.getenv("OPENAI_API_KEY")
    if args.chunking == "auto":
        args.chunking = pick_chunking()

    github = GitHubAPI("tqdm", "tqdm", os.getenv("GITHUB_API_KEY"))
    pipe = CP4Pipeline(github, make_embedder(args.embedder), NEWEST_SHA, OLDEST_SHA, embedder_name=args.embedder)
    cp4 = dict(chunking=args.chunking, use_filter=True, force_include=True, queries=MULTI_QUERIES, k=5)
    configs = [
        RetrievalConfig("A_cp3_baseline", queries=[CP3_QUERY]),
        RetrievalConfig("B_cp4_retrieval", **cp4),
        RetrievalConfig("C_cp4_concise", prompt_file=PROMPTS / "concise_prompt.md", **cp4),
        RetrievalConfig("D_cp4_structured", prompt_file=PROMPTS / "structured_prompt.md", **cp4),
    ]

    judge = LLMClient(llm_key, prompt_file=Path("src/llm_api/evaluator_prompt.md"))
    ground_truth = GROUND_TRUTH.read_text(encoding="utf-8")

    results = {}
    for cfg in configs:
        runs = []
        for i in range(1, args.repeats + 1):
            print(f"[{cfg.name}] run {i}/{args.repeats}: summarizing...")
            out = pipe.summarize(cfg, llm_key)
            (OUT_DIR / f"{cfg.name}_run{i}.md").write_text(out["response"], encoding="utf-8")

            print(f"[{cfg.name}] run {i}: judging...")
            raw = judge.generate_content(f"Ground Truth: {ground_truth} \n\nGenerated Summary: {out['response']}")
            try:
                audit = parse_judge_json(raw)
                score = rescore(audit)
            except (ValueError, json.JSONDecodeError):
                audit, score = {"unparsed": raw}, None
            json.dump(audit, open(OUT_DIR / f"{cfg.name}_run{i}_eval.json", "w"), indent=2)
            runs.append({"score": score, "words": len(out["response"].split()),
                         "commits_in_context": len(out["retrieved_shas"]),
                         "context_chars": out["context_chars"], "retrieved": out["retrieved_shas"]})
            print(f"   -> {score}")

        ok = [r for r in runs if r["score"]]
        mean = lambda key: round(statistics.mean(r["score"][key] for r in ok), 3) if ok else None
        results[cfg.name] = {
            "config": {"chunking": cfg.chunking, "filter": cfg.use_filter, "force_include": cfg.force_include,
                       "num_queries": len(cfg.queries), "k": cfg.k, "prompt": str(cfg.prompt_file)},
            "mean_recall": mean("recall"), "mean_precision": mean("precision"), "mean_f1": mean("f1"),
            "f1_runs": [r["score"]["f1"] for r in ok],
            "mean_words": round(statistics.mean(r["words"] for r in runs)),
            "commits_in_context": runs[0]["commits_in_context"],
            "judge_inconsistent_labels": sum(r["score"]["inconsistent_judge_labels"] for r in ok),
            "runs": runs,
        }

    json.dump(results, open(OUT_DIR / "prompt_results.json", "w"), indent=2)
    md = [f"# CP4 end-to-end comparison ({args.repeats} run(s) each, chunking for B-D: {args.chunking})", "",
          "Scored against the in-range ground truth (5 milestones from v2.2.4 + v3.1.4), re-scored strictly.", "",
          "| Config | Commits in context | Words | Recall | Precision | F1 (mean) | F1 per run |",
          "|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        md.append(f"| {name} | {r['commits_in_context']} | {r['mean_words']} | {r['mean_recall']} | "
                  f"{r['mean_precision']} | {r['mean_f1']} | {r['f1_runs']} |")
    (OUT_DIR / "prompt_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
