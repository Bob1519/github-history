# CP4 retrieval benchmark (embedder: bge-m3)

Filter: kept 70/96 commits, dropped 26; labelled-relevant commits dropped: none

## A. Milestone retrieval (6 milestones, each used as a query)

| Variant | Chunks | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|---|---|---|
| per_commit | 96 | 1.0 | 1.0 | 1.0 | 0.783 | 0.892 | 1.0 |
| per_commit+filter | 70 | 1.0 | 1.0 | 1.0 | 0.817 | 0.967 | 1.0 |
| per_file | 203 | 0.833 | 1.0 | 1.0 | 0.675 | 0.858 | 0.889 |
| per_file+filter | 126 | 0.833 | 1.0 | 1.0 | 0.75 | 0.967 | 0.917 |

## B. Coverage of the commits the pipeline sends to the LLM (k=5 per query)

| Variant | Queries | Commits in context | Milestones covered | Context precision |
|---|---|---|---|---|
| per_commit | cp3_single_query | 5 | 1/6 | 0.2 |
| per_commit | cp4_multi_query | 18 | 3/6 | 0.167 |
| per_commit+filter | cp3_single_query | 5 | 2/6 | 0.4 |
| per_commit+filter | cp4_multi_query | 18 | 5/6 | 0.389 |
| per_file | cp3_single_query | 5 | 1/6 | 0.2 |
| per_file | cp4_multi_query | 22 | 4/6 | 0.227 |
| per_file+filter | cp3_single_query | 5 | 1/6 | 0.2 |
| per_file+filter | cp4_multi_query | 17 | 4/6 | 0.294 |
