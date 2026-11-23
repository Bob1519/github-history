"""Checkpoint 5: multi-repository benchmark (tqdm, pallets/flask, fastapi/fastapi).

CP4 tuned the pipeline on a single tqdm range. This script checks whether the CP4 findings
(noise filter, per-commit chunking, multi-query retrieval, forced first/last/README) carry over
to two larger, better-documented projects whose maintainers publish detailed changelogs:

    flask    pallets/flask    3.0.3  -> 3.1.0    (118 commits, 47 merges, 10 changelog milestones)
    fastapi  fastapi/fastapi  0.99.0 -> 0.103.0  (155 commits, mostly docs/translations, 9 milestones)
    tqdm     tqdm/tqdm        v2.0.0 -> v3.1.4   (CP4 range, kept as the reference point)

Ground truth for each range is condensed from the maintainers' own release notes
(tests/test_ground_truth/<repo>_*_ground_truth.md) and every milestone is mapped to the commits
that implement it (<repo>_*_retrieval_labels.json; the labelling method is in each file).

Run from the repo root:
    python tests/cp5_benchmark.py --retrieval-only     # no OpenAI cost: filter + retrieval metrics
    python tests/cp5_benchmark.py                      # + end-to-end summaries, judged (gpt-4o-mini)
    python tests/cp5_benchmark.py --repos flask --repeats 1

Per repo it reports:
  * filter: commits kept/dropped, drop reasons, and whether any labelled commit was dropped
  * Part A (milestone retrieval): each milestone used as a query -> Hit@k, Recall@k, MRR
  * Part B (pipeline coverage): milestones with >= 1 labelled commit in the LLM context
  * Part C (end-to-end, skipped with --retrieval-only): A_cp3_baseline vs B_cp4_retrieval,
    each summary judged against the ground truth and re-scored in code (src/evaluation/rescore.py)

Outputs: tests/test_output/cp5/<repo>/ (summaries, judge audits, filter log, per-repo json)
         tests/test_output/cp5/benchmark_results.{json,md} (cross-repo tables)
"""
import argparse
import collections
import json
import os
import statistics
import time
from pathlib import Path

from cp4_common import ROOT, make_embedder
from dotenv import load_dotenv
from github_api.github_api import GitHubAPI
from pipeline.cp4_pipeline import CP3_QUERY, MULTI_QUERIES, CP4Pipeline, RetrievalConfig

OUT_DIR = ROOT / "tests" / "test_output" / "cp5"
GT_DIR = Path("tests/test_ground_truth")
KS = (1, 3, 5, 10)

REPOS = {
    "flask": {
        "owner": "pallets", "repo": "flask",
        "newest": "ab8149664182b662453a563161aa89013c806dc9",  # 3.1.0
        "oldest": "c12a5d874c5a014495eb2db8a73f40037bc813ac",  # 3.0.3
        "range": "3.0.3 -> 3.1.0",
        "ground_truth": GT_DIR / "flask_303_310_ground_truth.md",
        "labels": GT_DIR / "flask_303_310_retrieval_labels.json",
    },
    "fastapi": {
        "owner": "fastapi", "repo": "fastapi",
        "newest": "415eb1405a5bc93a32e14c15d690517c95d26743",  # 0.103.0
        "oldest": "983f1d34dbc9443fcd12159647aabdeabc5032a7",  # 0.99.0
        "range": "0.99.0 -> 0.103.0",
        "ground_truth": GT_DIR / "fastapi_099_103_ground_truth.md",
        "labels": GT_DIR / "fastapi_099_103_retrieval_labels.json",
    },
    "tqdm": {
        "owner": "tqdm", "repo": "tqdm",
        "newest": "d6ad58fe5ef7b1e838d8078963d9e890e32f3985",  # v3.1.4
        "oldest": "4d7aac956b414dd396ac807a8b19f30be15711ee",  # v2.0.0
        "range": "v2.0.0 -> v3.1.4",
        "ground_truth": GT_DIR / "tqdm_200_314_ground_truth_inrange.md",
        "labels": GT_DIR / "tqdm_200_314_retrieval_labels.json",
    },
}

# Part C configs. B is the CP4 winner (per-commit chunking, filter, forced inclusion, 5 themed
# queries, original analyzer prompt); A is the CP3 baseline it is compared against.
E2E_CONFIGS = [
    RetrievalConfig("A_cp3_baseline", queries=[CP3_QUERY]),
    RetrievalConfig("B_cp4_retrieval", chunking="per_commit", use_filter=True, force_include=True,
                    queries=MULTI_QUERIES, k=5),
]

short = lambda s: s[:7]


def filter_report(pipe: CP4Pipeline, labels):
    kept_short = {short(s) for s in pipe.kept_shas}
    range_short = {short(s) for s in pipe.range_shas}
    relevant_all = {r for m in labels for r in m["relevant"]}
    return {
        "total_commits": len(pipe.range_shas),
        "kept": len(pipe.kept_shas),
        "dropped": len(pipe.dropped),
        "drop_reasons": dict(collections.Counter(d["reason"].split(" (")[0] for d in pipe.dropped)),
        "labelled_commits_missing_from_range": sorted(relevant_all - range_short),
        "labelled_commits_dropped": sorted((relevant_all & range_short) - kept_short),
    }


def milestone_retrieval(pipe: CP4Pipeline, cfg: RetrievalConfig, labels):
    per_m = {}
    for m in labels:
        ranked = [short(s) for s in pipe.search_commits(cfg, m["query"], k=max(KS))]
        rel = set(m["relevant"])
        first = next((i + 1 for i, s in enumerate(ranked) if s in rel), None)
        per_m[m["id"]] = {
            **{f"hit@{k}": int(any(s in rel for s in ranked[:k])) for k in KS},
            **{f"recall@{k}": round(len(rel & set(ranked[:k])) / len(rel), 3) for k in KS},
            "rr": round(1 / first, 3) if first else 0.0,
            "top5": ranked[:5],
        }
    n = len(labels)
    summary = {f"hit@{k}": round(sum(v[f"hit@{k}"] for v in per_m.values()) / n, 3) for k in KS}
    summary.update({f"recall@{k}": round(sum(v[f"recall@{k}"] for v in per_m.values()) / n, 3) for k in KS})
    summary["mrr"] = round(sum(v["rr"] for v in per_m.values()) / n, 3)
    summary["num_chunks"] = len(pipe.store_for(cfg).commits)
    return {"summary": summary, "per_milestone": per_m}


def pipeline_coverage(pipe: CP4Pipeline, cfg: RetrievalConfig, labels):
    relevant_all = {r for m in labels for r in m["relevant"]}
    got = {short(s) for s in pipe.retrieve(cfg)}
    covered = [m["id"] for m in labels if got & set(m["relevant"])]
    rel_hit = len(got & relevant_all)
    return {
        "commits_in_context": len(got),
        "milestones_covered": len(covered),
        "milestones_total": len(labels),
        "covered_ids": covered,
        "missed_ids": [m["id"] for m in labels if m["id"] not in covered],
        "relevant_commits_in_context": rel_hit,
        "context_precision": round(rel_hit / len(got), 3) if got else 0.0,
    }


def end_to_end(pipe: CP4Pipeline, ground_truth: str, out_dir: Path, repeats: int, llm_key: str):
    from evaluation.rescore import parse_judge_json, rescore
    from llm_api.llm_client import LLMClient

    judge = LLMClient(llm_key, prompt_file=Path("src/llm_api/evaluator_prompt.md"))
    results = {}
    for cfg in E2E_CONFIGS:
        runs = []
        for i in range(1, repeats + 1):
            print(f"  [{cfg.name}] run {i}/{repeats}: summarizing...")
            out = pipe.summarize(cfg, llm_key)
            (out_dir / f"{cfg.name}_run{i}.md").write_text(out["response"], encoding="utf-8")
            print(f"  [{cfg.name}] run {i}: judging...")
            raw = judge.generate_content(f"Ground Truth: {ground_truth} \n\nGenerated Summary: {out['response']}")
            try:
                audit = parse_judge_json(raw)
                score = rescore(audit)
            except (ValueError, json.JSONDecodeError):
                audit, score = {"unparsed": raw}, None
            json.dump(audit, open(out_dir / f"{cfg.name}_run{i}_eval.json", "w"), indent=2)
            runs.append({"score": score, "words": len(out["response"].split()),
                         "commits_in_context": len(out["retrieved_shas"]),
                         "context_chars": out["context_chars"], "retrieved": out["retrieved_shas"]})
            print(f"     -> {score}")
        ok = [r for r in runs if r["score"]]
        mean = lambda key: round(statistics.mean(r["score"][key] for r in ok), 3) if ok else None
        results[cfg.name] = {
            "mean_recall": mean("recall"), "mean_precision": mean("precision"), "mean_f1": mean("f1"),
            "f1_runs": [r["score"]["f1"] for r in ok],
            "unparsed_runs": len(runs) - len(ok),
            "mean_words": round(statistics.mean(r["words"] for r in runs)),
            "commits_in_context": runs[0]["commits_in_context"],
            "context_chars": runs[0]["context_chars"],
            "judge_inconsistent_labels": sum(r["score"]["inconsistent_judge_labels"] for r in ok),
            "runs": runs,
        }
    return results


def run_repo(name: str, spec: dict, args, llm_key: str):
    print(f"\n===== {name}: {spec['owner']}/{spec['repo']} {spec['range']} =====")
    out_dir = OUT_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = json.load(open(spec["labels"]))["milestones"]

    t0 = time.perf_counter()
    github = GitHubAPI(spec["owner"], spec["repo"], os.getenv("GITHUB_API_KEY"))
    pipe = CP4Pipeline(github, make_embedder(args.embedder), spec["newest"], spec["oldest"],
                       embedder_name=args.embedder)
    fetch_s = round(time.perf_counter() - t0, 1)

    report = {"repo": f"{spec['owner']}/{spec['repo']}", "range": spec["range"],
              "newest_sha": spec["newest"], "oldest_sha": spec["oldest"],
              "num_milestones": len(labels), "embedder": args.embedder, "fetch_and_parse_s": fetch_s}
    report["filter"] = filter_report(pipe, labels)
    json.dump(pipe.dropped, open(out_dir / "filter_dropped.json", "w"), indent=2)
    print("[filter]", report["filter"])

    variants = [RetrievalConfig(f"{c}{'+filter' if f else ''}", chunking=c, use_filter=f)
                for c in args.chunkings for f in (False, True)]
    report["part_a_milestone_retrieval"] = {}
    for cfg in variants:
        report["part_a_milestone_retrieval"][cfg.name] = milestone_retrieval(pipe, cfg, labels)
        print(f"[A] {cfg.name:20s} {report['part_a_milestone_retrieval'][cfg.name]['summary']}")

    report["part_b_pipeline_coverage"] = {}
    for cfg in variants:
        for qname, queries in (("cp3_single_query", [CP3_QUERY]), ("cp4_multi_query", MULTI_QUERIES)):
            run = RetrievalConfig(cfg.name, chunking=cfg.chunking, use_filter=cfg.use_filter,
                                  queries=queries, k=5)
            key = f"{cfg.name} | {qname}"
            report["part_b_pipeline_coverage"][key] = pipeline_coverage(pipe, run, labels)
            print(f"[B] {key:40s} {report['part_b_pipeline_coverage'][key]}")

    if not args.retrieval_only:
        report["part_c_end_to_end"] = end_to_end(pipe, spec["ground_truth"].read_text(encoding="utf-8"),
                                                 out_dir, args.repeats, llm_key)
    json.dump(report, open(out_dir / f"results{suffix_for(args)}.json", "w"), indent=2)
    return report


def suffix_for(args) -> str:
    """bge-m3 is the reported embedder; smoke-test runs with 'hashing' get their own file names."""
    return "" if args.embedder == "bge-m3" else f"_{args.embedder}"


def write_markdown(reports: dict, args):
    md = [f"# CP5 multi-repository benchmark (embedder: {args.embedder})", "",
          "Ground truth: condensed maintainer changelogs; labels map each milestone to its commits "
          "(see tests/test_ground_truth/*_retrieval_labels.json).", "",
          "## Ranges and noise filter", "",
          "| Repo | Range | Commits | Kept | Dropped | Drop reasons | Milestones | Labelled commits dropped |",
          "|---|---|---|---|---|---|---|---|"]
    for name, r in reports.items():
        f = r["filter"]
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(f["drop_reasons"].items(), key=lambda x: -x[1]))
        md.append(f"| {name} | {r['range']} | {f['total_commits']} | {f['kept']} | {f['dropped']} | "
                  f"{reasons or '-'} | {r['num_milestones']} | {', '.join(f['labelled_commits_dropped']) or 'none'} |")
    missing = {n: r["filter"]["labelled_commits_missing_from_range"] for n, r in reports.items()
               if r["filter"]["labelled_commits_missing_from_range"]}
    if missing:
        md += ["", f"WARNING: labelled commits not found in the fetched range: {missing}"]

    md += ["", "## A. Milestone retrieval (each milestone used as a query)", "",
           "| Repo | Variant | Chunks | Hit@1 | Hit@5 | Recall@5 | Recall@10 | MRR |",
           "|---|---|---|---|---|---|---|---|"]
    for name, r in reports.items():
        for v, a in r["part_a_milestone_retrieval"].items():
            s = a["summary"]
            md.append(f"| {name} | {v} | {s['num_chunks']} | {s['hit@1']} | {s['hit@5']} | "
                      f"{s['recall@5']} | {s['recall@10']} | {s['mrr']} |")

    md += ["", "## B. Milestones with a labelled commit in the LLM context (k=5 per query)", "",
           "| Repo | Variant | Queries | Commits in context | Milestones covered | Context precision | Missed |",
           "|---|---|---|---|---|---|---|"]
    for name, r in reports.items():
        for key, b in r["part_b_pipeline_coverage"].items():
            variant, queries = key.split(" | ")
            md.append(f"| {name} | {variant} | {queries} | {b['commits_in_context']} | "
                      f"{b['milestones_covered']}/{b['milestones_total']} | {b['context_precision']} | "
                      f"{', '.join(b['missed_ids']) or '-'} |")

    if any("part_c_end_to_end" in r for r in reports.values()):
        md += ["", f"## C. End-to-end summaries judged against the ground truth ({args.repeats} run(s) each, gpt-4o-mini)", "",
               "Recall/precision/F1 are recomputed in code from the judge's per-item labels.", "",
               "| Repo | Config | Commits in context | Context chars | Words | Recall | Precision | F1 (mean) | F1 per run |",
               "|---|---|---|---|---|---|---|---|---|"]
        for name, r in reports.items():
            for cfg, c in r.get("part_c_end_to_end", {}).items():
                md.append(f"| {name} | {cfg} | {c['commits_in_context']} | {c['context_chars']:,} | {c['mean_words']} | "
                          f"{c['mean_recall']} | {c['mean_precision']} | {c['mean_f1']} | {c['f1_runs']} |")
    (OUT_DIR / f"benchmark_results{suffix_for(args)}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="+", default=list(REPOS), choices=list(REPOS))
    ap.add_argument("--retrieval-only", action="store_true", help="skip the OpenAI summaries and judge")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--chunkings", nargs="+", default=["per_commit", "per_file"], choices=["per_commit", "per_file"])
    ap.add_argument("--embedder", default="bge-m3", choices=["bge-m3", "hashing"])
    args = ap.parse_args()
    load_dotenv()
    os.chdir(ROOT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    llm_key = os.getenv("OPENAI_API_KEY")
    if not args.retrieval_only and not llm_key:
        raise SystemExit("OPENAI_API_KEY is not set; add it to .env or pass --retrieval-only")

    reports = {name: run_repo(name, REPOS[name], args, llm_key) for name in args.repos}
    json.dump(reports, open(OUT_DIR / f"benchmark_results{suffix_for(args)}.json", "w"), indent=2)
    write_markdown(reports, args)


if __name__ == "__main__":
    main()
