{
  "ground_truth_recall_audit": [
    {
      "milestone": "Support added for pandas apply => progress_apply",
      "status": "missed",
      "matching_narrative_excerpt": null
    },
    {
      "milestone": "80-char width when running interactive help()",
      "status": "missed",
      "matching_narrative_excerpt": null
    },
    {
      "milestone": "update examples using with syntax",
      "status": "missed",
      "matching_narrative_excerpt": null
    },
    {
      "milestone": "Added smoothing and maxinterval features for smooth progress bar and rate for unconstant, variable changes in update times",
      "status": "partially_covered",
      "matching_narrative_excerpt": "This included detailed descriptions of parameters such as `iterable`, `desc`, `total`, and new options like `smoothing`, which was introduced to provide users with better control over the progress bar's behavior."
    },
    {
      "milestone": "abstracted gui to its own class and file",
      "status": "missed",
      "matching_narrative_excerpt": null
    },
    {
      "milestone": "added a performance test to prevent performance regressions",
      "status": "missed",
      "matching_narrative_excerpt": null
    },
    {
      "milestone": "Added the dynamic management of the bar on window resize",
      "status": "covered",
      "matching_narrative_excerpt": "The introduction of `dynamic_ncols` marked a pivotal moment in the architectural evolution of `tqdm`. This feature required changes in multiple files, including `tqdm/_tqdm.py` and `tqdm/_utils.py`."
    },
    {
      "milestone": "better internal testing/build workflow using python setup.py make [alias]",
      "status": "covered",
      "matching_narrative_excerpt": "The commit `bee450d` on October 13, 2015, introduced a cleaner build process in the `Makefile`, consolidating various commands and making it easier for developers to manage the project."
    }
  ],
  "narrative_precision_audit": [
    {
      "narrative_claim": "improve documentation",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    },
    {
      "narrative_claim": "extensive modifications to `README.rst`",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    },
    {
      "narrative_claim": "added clarity to the parameters of the `tqdm` class",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    },
    {
      "narrative_claim": "dynamic_ncols parameter",
      "matches_ground_truth": true,
      "matched_milestone": "Added the dynamic management of the bar on window resize"
    },
    {
      "narrative_claim": "integration of testing into the development process",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    },
    {
      "narrative_claim": "new tests were added to validate the behavior of the progress bar",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    },
    {
      "narrative_claim": "commands for running tests and checking code quality",
      "matches_ground_truth": false,
      "matched_milestone": "none - noise/unverified"
    }
  ],
  "counts": {
    "total_gt_milestones": 7,
    "covered_milestones": 2,
    "partially_covered_milestones": 1,
    "missed_milestones": 4,
    "total_narrative_claims": 7,
    "matched_narrative_claims": 1
  },
  "metrics": {
    "end_to_end_recall": 0.214,
    "end_to_end_precision": 0.143,
    "pipeline_f1_score": 0.174
  }
}