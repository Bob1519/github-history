from github_api.github_api import GitHubAPI
import os
import json
from dotenv import load_dotenv

load_dotenv()

GITHUB_API_TOKEN = os.getenv("GITHUB_API_KEY")
#extractor = GitHubAPI(owner="Bob1519", repo="CS4240-Project3", github_api_key=GITHUB_API_TOKEN)
extractor = GitHubAPI(owner="tqdm", repo="tqdm", github_api_key=GITHUB_API_TOKEN)

#all_shas = extractor.fetch_all_commit_shas()
#commit = extractor.get_commit(all_shas[0])

output = extractor.get_all_processed_commits()

with open("test.json", "w", encoding="utf-8") as f:
    json.dump(output,f, indent = 2)