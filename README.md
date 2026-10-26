# github-history
A tool to analyze github repositories

## Setup Steps

### 1. Create a Virtual Environment

Initialize a virtual environment in the project root directory:

```bash
conda create --file environment.yml  
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
python ./src/github_api_test.py

# Test LLM client
python ./src/llm_client_test.py

#Test the FAISS database
python ./src/faiss_init_test.py

#Test the tqdm pipeline result
python tests/tqdm_200_314_test.py  
```


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
