from llm_api.llm_client import LLMClient
from vector_store.faiss_index import CommitVectorStore, INDEX_TYPES, _normalize
from github_api.github_api import GitHubAPI
import faiss
import numpy as np
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

class Pipeline:
    def __init__(self, github_api: GitHubAPI, vector_store: CommitVectorStore, llm_client: LLMClient):
        self.github = github_api
        self.vector_store = vector_store
        self.llm = llm_client
        self.commits = None
        self.context = ""
    
    def set_vector_store(self):
        self.commits = self.github.get_all_processed_commits() 
    
    def set_vector_store_commit(self, start_commit: str = None, end_commit: str = None):
        self.set_vector_store()
        commit_shas = self.github.fetch_all_commit_shas()
        start_index = commit_shas.index(end_commit)
        end_index = commit_shas.index(start_commit)
        
        self.commits = self.commits[start_index:end_index + 1]
        
        self.vector_store.build(self.commits, use_cache=True, save=True)
    
    def run(self):
        self.search = self.vector_store.search("Major Architectural features refactors milestones releases")
        self.generate_context()
        _, response = self.llm.generate_content(self.context)
        with open("response.md", "w", encoding="utf-8") as f:
            f.write(response)
    
    def generate_context(self):
        self.context = f"Repo: {self.github.repo} \nOwner: {self.github.owner}\n"
        for commit in self.search:
            self.context += "\n" + commit["llm_summary"]
        
        
        
        
        
            
        
        
        
        