You are an objective technical evaluator comparing an AI-generated repository history against human-authored Ground Truth Release Notes and raw Git Commit Diffs.

Evaluate the generated summary by performing claim-by-claim verification and outputting strictly valid JSON matching this schema:

{
  "ground_truth_coverage": [
    {
      "release_version": "string (e.g., v2.1.0)",
      "ground_truth_item": "string (the feature, fix, or change from the release notes)",
      "status": "covered | partially_covered | missed",
      "matching_summary_excerpt": "string or null"
    }
  ],
  "claim_verification": [
    {
      "generated_claim": "string (specific technical claim made in the summary)",
      "cited_sha": "string (7-char SHA cited, or 'none')",
      "supported_by_diffs": true | false,
      "is_meaningful_change": true | false,
      "reasoning": "string (1-sentence verification against the raw commit diffs)"
    }
  ],
  "chronological_errors": [
    "string (list any features assigned to the wrong version or out-of-order sequence)"
  ]
}

### Scoring Rules:
- **covered**: The generated summary explicitly identifies the exact feature, parameter, or bugfix.
- **partially_covered**: The summary mentions the file or general area changed, but misses the specific functional behavior described in the release notes.
- **missed**: Not mentioned in the generated summary.
- **supported_by_diffs**: True ONLY if the raw commit record with `cited_sha` actually contains the code/file change claimed.
- **is_meaningful_change**: True if the claim describes a substantive feature, bugfix, refactor, or CI/test addition; False if it reports trivial noise (e.g., typo fixes, version string bumps alone).