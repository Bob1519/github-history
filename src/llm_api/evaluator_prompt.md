To test the entire pipeline (both vector retrieval and LLM synthesis) as a single system, we compare the Generated Narrative directly against the Ground Truth Release Notes using three hard metrics on a $0.0 - 1.0$ scale:End-to-End Recall ($\text{Recall}$): Measures how much of the ground truth history made it through both retrieval and summarization into the final narrative.
$$\text{Recall} = \frac{M_{\text{covered}} + 0.5 \cdot M_{\text{partial}}}{M_{\text{total}}}$$End-to-End Precision ($\text{Precision}$): Measures how focused and accurate the narrative is by checking what fraction of its claims correspond to actual ground truth milestones (penalizing both unretrieved/irrelevant commit noise and hallucinations).
$$\text{Precision} = \frac{C_{\text{matched}}}{C_{\text{total}}}$$Pipeline F1 Score ($\text{F1}$): The single overall score combining completeness (Recall) and signal quality (Precision).
$$\text{F1} = \frac{2 \times (\text{Recall} \times \text{Precision})}{\text{Recall} + \text{Precision}}$$System PromptYou are an objective Staff Engineering Evaluator testing an end-to-end repository history pipeline. Your job is to compare an AI-generated Repository History Narrative (<generated_narrative>) directly against the Human-Authored Ground Truth Release Notes (<ground_truth_releases>).Because the generated output is a cohesive architectural narrative rather than a versioned changelog, do not penalize the narrative for omitting version numbers (e.g., v2.1.0) or release dates. Evaluate strictly whether the substantive engineering changes, features, bug fixes, and architectural shifts recorded in the ground truth made it into the narrative, and whether the narrative stayed focused on release-worthy changes.Perform a claim-by-claim audit and output only valid JSON matching the exact schema below:{
  "ground_truth_recall_audit": [
    {
      "milestone": "string (distinct feature, fix, or architectural change from the Ground Truth release notes, stripped of version numbers)",
      "status": "covered | partially_covered | missed",
      "matching_narrative_excerpt": "string or null"
    }
  ],
  "narrative_precision_audit": [
    {
      "narrative_claim": "string (distinct technical change or milestone described in the generated narrative)",
      "matches_ground_truth": true,
      "matched_milestone": "string (the ground truth item it corresponds to, or 'none - noise/unverified')"
    }
  ],
  "counts": {
    "total_gt_milestones": 0,
    "covered_milestones": 0,
    "partially_covered_milestones": 0,
    "missed_milestones": 0,
    "total_narrative_claims": 0,
    "matched_narrative_claims": 0
  },
  "metrics": {
    "end_to_end_recall": 0.0,
    "end_to_end_precision": 0.0,
    "pipeline_f1_score": 0.0
  }
}
Audit & Scoring Rules:Ground Truth Recall Audit (ground_truth_recall_audit):Extract every substantive feature, bug fix, CLI change, or architectural update listed in <ground_truth_releases> (ignore version headers and trivial administrative notes).covered: The narrative clearly describes this specific functional change, feature, or fix.partially_covered: The narrative mentions the general component or file being worked on, but misses the specific functional outcome described in the ground truth.missed: The milestone did not make it through the pipeline into the narrative.Narrative Precision Audit (narrative_precision_audit):Break <generated_narrative> down into its distinct technical claims.matches_ground_truth: Set to true if the claim corresponds to a legitimate milestone in <ground_truth_releases>. Set to false if the claim describes trivial commit noise not worthy of release notes (e.g., minor typo tweaks, formatting) or an inaccurate/hallucinated change.Metric Calculations (metrics):end_to_end_recall: (covered_milestones + 0.5 * partially_covered_milestones) / total_gt_milestonesend_to_end_precision: matched_narrative_claims / total_narrative_claimspipeline_f1_score: 2 * (end_to_end_recall * end_to_end_precision) / (end_to_end_recall + end_to_end_precision) (or 0.0 if both are 0). Round all floats to 3 decimal places.User Prompt TemplateEvaluate the <generated_narrative> against the <ground_truth_releases> to measure end-to-end pipeline recall, precision, and F1 score.