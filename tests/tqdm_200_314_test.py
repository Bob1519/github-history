from llm_api.llm_client import LLMClient
from vector_store.faiss_index import CommitVectorStore
from github_api.github_api import GitHubAPI
from pipeline.pipeline import Pipeline
from evaluation.evaluation import Evaluator
import faiss
import numpy as np
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pathlib import Path

###
# This test runs against ~100 commits from tqdm version 2.0.0 to version 3.1.4
###

load_dotenv()

GROUND_TRUTH_PATH = Path("tests/test_ground_truth/tqdm_200_314_ground_truth.md")
SAVE_PATH = Path("tests/test_output/tqdm_200_314_results.json")

GITHUB_API_TOKEN = os.getenv("GITHUB_API_KEY")

LLM_API_KEY = os.getenv("OPENAI_API_KEY")

pipeline = Pipeline("tqdm", "tqdm", GITHUB_API_TOKEN, LLM_API_KEY)
pipeline.set_vector_store_commit("4d7aac956b414dd396ac807a8b19f30be15711ee", "d6ad58fe5ef7b1e838d8078963d9e890e32f3985")
response = pipeline.generate_summary()

evaluator = Evaluator(LLM_API_KEY, SAVE_PATH, GROUND_TRUTH_PATH)
# with open("src/llm_api/response.md", "r", encoding="utf-8") as f:
#     response = f.read()
evaluator.evaluate(response)