from llm_api.llm_client import LLMClient
from vector_store.faiss_index import CommitVectorStore, INDEX_TYPES, _normalize
from github_api.github_api import GitHubAPI
from pipeline.pipeline import Pipeline
import faiss
import numpy as np
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

###
# This test runs against ~100 commits from tqdm version 2.0.0 to version 3.1.4
###

load_dotenv()

GITHUB_API_TOKEN = os.getenv("GITHUB_API_KEY")
extractor = GitHubAPI(owner="tqdm", repo="tqdm", github_api_key=GITHUB_API_TOKEN)

LLM_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = LLMClient(LLM_API_KEY)

model = SentenceTransformer("BAAI/bge-m3", local_files_only=True)
def embed_fn(texts: list[str]) -> list[list[float]]:
    return model.encode(texts).tolist()
store = CommitVectorStore(embed_fn, name="tqdm", index_type="flat")

pipeline = Pipeline(extractor, store, openai_client)
pipeline.set_vector_store_commit("4d7aac956b414dd396ac807a8b19f30be15711ee", "d6ad58fe5ef7b1e838d8078963d9e890e32f3985")
pipeline.run()