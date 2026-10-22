from llm_api.llm_client import LLMClient
from vector_store.faiss_index import CommitVectorStore
from github_api.github_api import GitHubAPI
from sentence_transformers import SentenceTransformer

class Pipeline:
    def __init__(self, owner: str, repo: str, github_api_key: str, llm_key: str):
        model = SentenceTransformer("BAAI/bge-m3", local_files_only=True)
        def embed_fn(texts: list[str]) -> list[list[float]]:
            return model.encode(texts).tolist()
        
        self.github = GitHubAPI(owner=owner, repo=repo, github_api_key=github_api_key)
        
        self.vector_store = CommitVectorStore(embed_fn, name=repo, index_type="flat")
        
        self.llm = LLMClient(llm_key)
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
        response = self.llm.generate_content(self.context)
        with open("response.md", "w", encoding="utf-8") as f:
            f.write(response)
    
    def generate_context(self):
        self.context = f"Repo: {self.github.repo} \nOwner: {self.github.owner}\n"
        for commit in self.search:
            self.context += "\n" + commit["llm_summary"]
        
        
        
        
        
            
        
        
        
        