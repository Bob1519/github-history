# github-history
A tool to analyze github repositories

## Setup Steps

### 1. Create a Virtual Environment

Initialize a virtual environment in the project root directory:

```bash
# macOS / Linux
python3 -m venv .venv

# Windows
python -m venv .venv
```

### 2. Activate the Virtual Environment

Activate the environment according to your operating system:

* **macOS / Linux:**
  ```bash
  source .venv/bin/activate
  ```

* **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
### 3. Install Dependencies

Use pip to install all required packages:

```bash
pip install -r requirements.txt
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
```


## Checkpoints

Checkpoint 1:
Plan was created and Repo was initialized

Checkpoint 2:

Created github_api which contains function to request sha and commit information as well as caching it to save on requests. It also formats the commits for human and embedding use.

Created llm_client which initializes the openAI client and allows for basic prompting

Things to test/change: The Embedding limits the amount of code from each file allowed into the summary and how many diff files are allowed in. For certain files, this cuts off information. May want to test how much of the file we allow into the embedding summary
