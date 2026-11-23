# github-history
A tool to analyze github repositories

## Setup Steps

### 1. Create a Virtual Environment

Initialize a virtual environment in the project root directory:

```bash
conda env create -f environment.yml
```

### 2. Activate the Virtual Environment

Activate the environment according to your operating system:
  ```bash
  conda activate history_env
  ```
### 3. Configure Packages

Use pip to configure the packages
```bash
pip install --no-build-isolation --no-deps -e .
```
### 4. Configure Environment Variables

Create a local `.env` configuration file from the template:

* **macOS / Linux:**
  ```bash
  cp .env_example .env
  ```

* **Windows:**
  ```cmd
  copy .env_example .env
  ```

Open `.env` in an editor and enter your credentials:

```env
GITHUB_API_KEY=your_github_personal_access_token_here
OPENAI_API_KEY=your_openai_api_key_here
```
### 5. Running the Scripts

Execute the pipeline components from the activated virtual environment:

```bash
# test github API
python tests/github_api_test.py

# Test LLM client
python tests/llm_client_test.py

#Test the FAISS database
python tests/faiss_init_test.py

#Test the tqdm pipeline result
python tests/tqdm_200_314_test.py  
```

### 6. Checkpoint 4 experiments (run from the repo root)

```bash
# 1) Chunking (per-commit vs per-file) x noise filter retrieval benchmark. No OpenAI cost, ~5-15 min on CPU.
python tests/cp4_retrieval_benchmark.py

# 2) End-to-end comparison of CP3 baseline vs CP4 retrieval and 3 prompts (gpt-4o-mini, a few cents).
#    Automatically uses the chunking strategy that won step 1.
python tests/cp4_prompt_comparison.py
```

Results are written to `tests/test_output/cp4/` (`retrieval_results.md`, `prompt_results.md`,
`filter_dropped.json`, and each generated summary with its judge output).

## 7. Running the UI

```bash
streamlit run app.py
```

Opens a local web page (http://localhost:8501). Pick a cached repo or type any `owner/repo`, click
**Load / Refresh Commits**, then work through the four tabs: (1) commit range + noise filter,
(2) FAISS index + retrieval, (3) LLM summary, (4) LLM judge + deterministic re-scoring against a
ground-truth file. **Run Full Pipeline** in the sidebar does tabs 1-3 in one click. The default
range is the newest 200 commits, because each uncached commit costs one GitHub API call.

The first bge-m3 run downloads the model (~2.3 GB) into the Hugging Face cache; later runs are offline.

## 8. Checkpoint 5 multi-repository benchmark

```bash
# Filter + retrieval metrics on flask, fastapi and tqdm. No OpenAI cost.
# First run pulls ~280 commits plus the full SHA lists from GitHub (~410 requests, needs a token).
python tests/cp5_benchmark.py --retrieval-only

# Full run: also generates summaries (CP3 baseline vs CP4 config, 2 runs each) and judges them.
python tests/cp5_benchmark.py
```

| Repo | Range | Ground truth |
|---|---|---|
| pallets/flask | 3.0.3 -> 3.1.0 | `tests/test_ground_truth/flask_303_310_*` (10 milestones, from CHANGES.rst) |
| fastapi/fastapi | 0.99.0 -> 0.103.0 | `tests/test_ground_truth/fastapi_099_103_*` (9 milestones, from release-notes.md) |
| tqdm/tqdm | v2.0.0 -> v3.1.4 | `tests/test_ground_truth/tqdm_200_314_*` (CP4 range) |

Results go to `tests/test_output/cp5/benchmark_results.md` / `.json`, with per-repo summaries,
judge audits and filter logs in `tests/test_output/cp5/<repo>/`. `--embedder hashing` is an
offline smoke test only; its outputs are written with a `_hashing` suffix and are not reported.


## Checkpoints

Checkpoint 1:
Plan was created and Repo was initialized

Checkpoint 2:

Created github_api which contains function to request sha and commit information as well as caching it to save on requests. It also formats the commits for human and embedding use.

Created llm_client which initializes the openAI client and allows for basic prompting

Things to test/change: The Embedding limits the amount of code from each file allowed into the summary and how many diff files are allowed in. For certain files, this cuts off information. May want to test how much of the file we allow into the embedding summary

FAISS initialization (added to Checkpoint 2 work):

`src/faiss_init_test.py` creates a FAISS index (`IndexFlatIP`), adds a small set of words as vectors, searches it, then saves the index to disk and reloads it to confirm identical results. No API key is needed. Run `python ./src/faiss_init_test.py`; output is in `checkpoint_factual/checkpoint_2/` (`faiss_init_results.json`, `words.faiss`). The word vectors are a placeholder (hashed character trigrams), not a semantic model.

Groundwork for the embedding checkpoint (not yet part of the pipeline):

`src/vector_store/faiss_index.py` (`CommitVectorStore`) and `LLMClient.embed()` embed commit text, build/save/load a FAISS index and return top-k search results; `src/faiss_test.py` runs and benchmarks it (needs `OPENAI_API_KEY`, or `--offline` for a low-quality local embedder). Commit chunking is not implemented yet; the store currently embeds one vector per commit.

Checkpoint 3: Created the main pipeline implementation.

Checkpoint 4: Chunking comparison (per-commit vs per-file), noise filter, forced inclusion of first/last commit and README, multi-query retrieval, deterministic re-scoring of the LLM judge.

Checkpoint 5: Streamlit UI over the CP4 pipeline (`app.py`, `src/ui/`) and a multi-repository benchmark on pallets/flask and fastapi/fastapi with changelog-derived ground truth (`tests/cp5_benchmark.py`).
