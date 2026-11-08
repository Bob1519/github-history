"""Checkpoint 4, experiment 1: chunking x filtering retrieval accuracy on tqdm v2.0.0 -> v3.1.4.

No OpenAI calls -- only GitHub cache + local bge-m3 embeddings. Run from the repo root:
    python tests/cp4_retrieval_benchmark.py

Part A (milestone retrieval): each ground-truth milestone is used as a query; we measure whether
its labelled commits are retrieved. Hit@k = at least one relevant commit in the top k,
Recall@k = fraction of the relevant commits in the top k, MRR = 1 / rank of first relevant commit.

Part B (pipeline coverage): the queries the pipeline actually uses (CP3 single query vs the CP4
multi-query set) -- how many milestones end up with at least one relevant commit in the LLM context.

Outputs: tests/test_output/cp4/retrieval_results.json, retrieval_results.md, filter_dropped.json
"""
import argparse
import json
import os

from cp4_common import NEWEST_SHA, OLDEST_SHA, OUT_DIR, ROOT, make_embedder
from dotenv import load_dotenv
from github_api.github_api import GitHubAPI
from pipeline.cp4_pipeline import CP3_QUERY, MULTI_QUERIES, CP4Pipeline, RetrievalConfig

KS = (1, 3, 5, 10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", default="bge-m3", choices=["bge-m3", "hashing"])
    args = ap.parse_args()
    load_dotenv()
    os.chdir(ROOT)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    labels = json.load(open("tests/test_ground_truth/tqdm_200_314_retrieval_labels.json"))["milestones"]
    github = GitHubAPI("tqdm", "tqdm", os.getenv("GITHUB_API_KEY"))
    pipe = CP4Pipeline(github, make_embedder(args.embedder), NEWEST_SHA, OLDEST_SHA, embedder_name=args.embedder)
    short = lambda s: s[:7]

    # ----- filter report -----
    kept_short = {short(s) for s in pipe.kept_shas}
    relevant_all = {r for m in labels for r in m["relevant"]}
    wrongly_dropped = sorted(relevant_all - kept_short)
    json.dump(pipe.dropped, open(OUT_DIR / "filter_dropped.json", "w"), indent=2)
    filter_report = {"total_commits": len(pipe.range_shas), "kept": len(pipe.kept_shas),
                     "dropped": len(pipe.dropped), "relevant_commits_dropped": wrongly_dropped}
    print("[filter]", filter_report)

    variants = [RetrievalConfig(f"{c}{'+filter' if f else ''}", chunking=c, use_filter=f)
                for c in ("per_commit", "per_file") for f in (False, True)]

    # ----- Part A: milestone retrieval -----
    part_a = {}
    for cfg in variants:
        ranked_cache = {}
        per_m = {}
        for m in labels:
            ranked = [short(s) for s in pipe.search_commits(cfg, m["query"], k=max(KS))]
            ranked_cache[m["id"]] = ranked
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
        part_a[cfg.name] = {"summary": summary, "per_milestone": per_m}
        print(f"[A] {cfg.name:22s} {summary}")

    # ----- Part B: what the pipeline's own queries put in the LLM context -----
    part_b = {}
    for cfg in variants:
        for qname, queries in (("cp3_single_query", [CP3_QUERY]), ("cp4_multi_query", MULTI_QUERIES)):
            run = RetrievalConfig(cfg.name, chunking=cfg.chunking, use_filter=cfg.use_filter,
                                  queries=queries, k=5)
            got = {short(s) for s in pipe.retrieve(run)}
            covered = [m["id"] for m in labels if got & set(m["relevant"])]
            rel_hit = len(got & relevant_all)
            part_b[f"{cfg.name} | {qname}"] = {
                "commits_in_context": len(got),
                "milestones_covered": len(covered),
                "milestones_total": len(labels),
                "covered_ids": covered,
                "relevant_commits_in_context": rel_hit,
                "context_precision": round(rel_hit / len(got), 3) if got else 0.0,
            }
            print(f"[B] {cfg.name:22s} {qname:17s} {part_b[f'{cfg.name} | {qname}']}")

    results = {"embedder": args.embedder, "filter": filter_report, "part_a_milestone_retrieval": part_a,
               "part_b_pipeline_coverage": part_b}
    json.dump(results, open(OUT_DIR / "retrieval_results.json", "w"), indent=2)

    # ----- markdown tables for the report -----
    md = [f"# CP4 retrieval benchmark (embedder: {args.embedder})", "",
          f"Filter: kept {filter_report['kept']}/{filter_report['total_commits']} commits, "
          f"dropped {filter_report['dropped']}; labelled-relevant commits dropped: "
          f"{wrongly_dropped or 'none'}", "",
          "## A. Milestone retrieval (6 milestones, each used as a query)", "",
          "| Variant | Chunks | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Recall@10 | MRR |",
          "|---|---|---|---|---|---|---|---|"]
    for name, r in part_a.items():
        s = r["summary"]
        md.append(f"| {name} | {s['num_chunks']} | {s['hit@1']} | {s['hit@3']} | {s['hit@5']} | "
                  f"{s['recall@5']} | {s['recall@10']} | {s['mrr']} |")
    md += ["", "## B. Coverage of the commits the pipeline sends to the LLM (k=5 per query)", "",
           "| Variant | Queries | Commits in context | Milestones covered | Context precision |",
           "|---|---|---|---|---|"]
    for name, r in part_b.items():
        v, q = name.split(" | ")
        md.append(f"| {v} | {q} | {r['commits_in_context']} | {r['milestones_covered']}/{r['milestones_total']} | "
                  f"{r['context_precision']} |")
    (OUT_DIR / "retrieval_results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\nWrote", OUT_DIR / "retrieval_results.md")


if __name__ == "__main__":
    main()
