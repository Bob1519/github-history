# CP4 end-to-end comparison (2 run(s) each, chunking for B-D: per_commit)

Scored against the in-range ground truth (5 milestones from v2.2.4 + v3.1.4), re-scored strictly.

| Config | Commits in context | Words | Recall | Precision | F1 (mean) | F1 per run |
|---|---|---|---|---|---|---|
| A_cp3_baseline | 5 | 512 | 0.3 | 0.167 | 0.182 | [0.364, 0.0] |
| B_cp4_retrieval | 19 | 606 | 0.45 | 0.615 | 0.52 | [0.686, 0.353] |
| C_cp4_concise | 19 | 248 | 0.45 | 0.278 | 0.342 | [0.429, 0.255] |
| D_cp4_structured | 19 | 442 | 0.5 | 0.225 | 0.309 | [0.286, 0.333] |
