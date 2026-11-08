"""Checkpoint 4: stricter, deterministic scoring of the LLM judge's audit.

In CP3 the judge computed recall/precision itself, and its audit was internally inconsistent:
several narrative claims were marked "matches_ground_truth": true while their matched_milestone
was "none - noise/unverified", which inflated precision. Here we keep the judge's per-item
labels but recompute every count and metric in Python:

  - a narrative claim only counts as matched if matches_ground_truth is true AND it names a
    real milestone (matched_milestone does not start with "none")
  - recall / precision / F1 are recomputed from the audit lists, not taken from the judge
"""
import json
import re
from typing import Dict


def parse_judge_json(text) -> Dict:
    if isinstance(text, dict):
        return text
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def rescore(audit: Dict) -> Dict:
    recall_items = audit.get("ground_truth_recall_audit", [])
    claims = audit.get("narrative_precision_audit", [])

    covered = sum(1 for m in recall_items if m.get("status") == "covered")
    partial = sum(1 for m in recall_items if m.get("status") == "partially_covered")
    total_gt = len(recall_items)

    def is_matched(c):
        milestone = str(c.get("matched_milestone") or "").strip().lower()
        return bool(c.get("matches_ground_truth")) and milestone and not milestone.startswith("none")

    matched = sum(1 for c in claims if is_matched(c))
    inconsistent = sum(1 for c in claims if c.get("matches_ground_truth") and not is_matched(c))

    recall = (covered + 0.5 * partial) / total_gt if total_gt else 0.0
    precision = matched / len(claims) if claims else 0.0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) else 0.0

    judge_metrics = audit.get("metrics", {})
    return {
        "total_gt_milestones": total_gt, "covered": covered, "partially_covered": partial,
        "total_claims": len(claims), "matched_claims": matched,
        "inconsistent_judge_labels": inconsistent,
        "recall": round(recall, 3), "precision": round(precision, 3), "f1": round(f1, 3),
        "judge_reported_f1": judge_metrics.get("pipeline_f1_score"),
    }
