import requests
from pathlib import Path
from typing import List, Dict
import os
import json
from dotenv import load_dotenv
import re

class GitHubAPI():
    def __init__(self, owner: str, repo: str, github_api_key: str = None):
        self.owner = owner
        self.repo = repo
        self.base_url = "https://api.github.com"
        self.cache_dir = Path("github_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        if github_api_key:
            self.headers["Authorization"] = f"Bearer {github_api_key}"
    
    def is_rate_limited(self, err: requests.exceptions.HTTPError) -> bool:
        return err.response is not None and err.response.status_code in (403, 429)
            
    
    def fetch_commit_page(self, page: int = 1, per_page: int = 100, use_cache: bool = True) -> List[str]:
        cache_file = self.cache_dir / f"{self.repo}_commit_page_{page}_limit_{per_page}.json"
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/commits"
        
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        res = requests.get(url, headers=self.headers, params={"page": page, "per_page":per_page})
        
        res.raise_for_status()
        
        shas = [c["sha"] for c in res.json()]
        
        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(shas, f)
        
        return shas

    def fetch_all_commit_shas(self, max_commits = None, use_cache: bool = True):
        if max_commits:
            cache_file = self.cache_dir / f"{self.repo}_{max_commits}_shas.json"
        else:
            cache_file = self.cache_dir / f"{self.repo}_all_shas.json"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        all_shas: List[str] = []
        page = 1
        per_page = 100
        rate_limit = False
        
        while True:
            try:
                page_shas = self.fetch_commit_page(page = page, per_page=per_page, use_cache=use_cache)
            except requests.exceptions.HTTPError as err:
                if self.is_rate_limited(err):
                    print(f"Warning: SHA collection halted by rate limit: {err}")
                    rate_limit = True
                    break
                raise err
            
            if not page_shas:
                break
            
            all_shas.extend(page_shas)
            
            if max_commits and len(all_shas) >= max_commits:
                return all_shas[:max_commits]

            if len(page_shas) < per_page:
                break
                
            page += 1
        
        if not rate_limit and use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(all_shas, f)
        
        return all_shas
    
    def get_commit(self, sha: str, use_cache: bool = True) -> Dict:
        cache_file = self.cache_dir / f"{self.repo}_commit_{sha}.json"
        if cache_file.exists() and use_cache:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        url = f"{self.base_url}/repos/{self.owner}/{self.repo}/commits/{sha}"
        res = requests.get(url, headers=self.headers)
        
        res.raise_for_status()
        
        data = res.json()
        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        return data

    def _sanitize_diff_lines(self, patch: str, max_lines_per_file: int = 15):
        important_lines = []
        for line in patch.splitlines():
            if line.startswith(("---", "+++", "@@")):
                continue
            if line.startswith(("+", "-")) and line[1:].strip():
                clean_line = line[0]+ " " + line[1:].strip()
                important_lines.append(clean_line)
                if len(important_lines) > max_lines_per_file:
                    break
        return important_lines
    
    def parse_commit(self, commit_data: Dict[str, any], use_cache: bool = True) -> Dict[str, any]:
        sha = commit_data["sha"]
        author = commit_data.get("commit", {}).get("author", {}).get("name", "Unknown")
        date = commit_data.get("commit", {}).get("author", {}).get("date", "")
        message = commit_data.get("commit", {}).get("message", "").strip()
        
        cache_file = self.cache_dir / f"{self.repo}_processed_{sha}.json"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        files_meta_data = []
        diff_snippets = []
        files = commit_data.get("files", [])
        
        for f in files:
            filename = f.get("filename", "")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            files_meta_data.append(f"{filename} (+{additions}, -{deletions})")
            
            if re.search(r"(\.lock|package-lock\.json|\.svg|\.min\.js)$", filename):
                continue
            
            patch = f.get("patch", "")
            if patch:
                cleaned_patch = self._sanitize_diff_lines(patch, 15)
                if cleaned_patch and len(diff_snippets) < 5:
                    diff_snippets.append(
                        f"--- {filename} ---\n" + "\n".join(cleaned_patch)
                    )

        files_summary = ", ".join(files_meta_data[:8])
        if len(files_meta_data) > 8:
            files_summary += f", ... (+{len(files_meta_data) - 8} more)"
            
        raw_diff_summary = "\n\n".join(diff_snippets)
        
        embedding_summary = (
            f"Commit: {sha}\n"
            f"Author: {author}\n"
            f"Date: {date}\n"
            f"Message: {message}\n"
            f"Affected Files: {files_summary}\n"
            f"Summary Diff:\n{raw_diff_summary}"
        )
        
        parsed_commit = {
            "sha": sha,
            "date": date,
            "author": author,
            "message": message,
            "files": [f.get("filename") for f in files],
            "embedding_text": embedding_summary
        }
        
        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(parsed_commit, f, indent=2)
        
        return parsed_commit
            
    def get_all_processed_commits(self, max_commits: int = None, use_cache: bool = True) -> List[Dict[str, any]]:
        if max_commits:
            cache_file = self.cache_dir / f"{self.repo}_{max_commits}_processed_commits.json"
        else:
            cache_file = self.cache_dir / f"{self.repo}_all_processed_commits.json"
            
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        
        shas = self.fetch_all_commit_shas(max_commits=max_commits, use_cache=use_cache)
        parsed_commits = []
        rate_limited = False
        for sha in shas:
            try:
                commit = self.get_commit(sha, use_cache=use_cache)
                parsed_commit = self.parse_commit(commit, use_cache=use_cache)
                parsed_commits.append(parsed_commit)
            except requests.exceptions.HTTPError as err:
                if self.is_rate_limited(err):
                    print(f"[WARNING] Error due to rate limit {err}")
                    rate_limited = True
                    break
                raise err
        
        if not rate_limited and use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(parsed_commits, f, indent=2)
        
        return parsed_commits
    
if __name__ == "__main__":
    load_dotenv()
    
    GITHUB_API_TOKEN = os.getenv("GITHUB_API_KEY")
    #extractor = GitHubAPI(owner="Bob1519", repo="CS4240-Project3", github_api_key=GITHUB_API_TOKEN)
    extractor = GitHubAPI(owner="tqdm", repo="tqdm", github_api_key=GITHUB_API_TOKEN)
    
    #all_shas = extractor.fetch_all_commit_shas()
    #commit = extractor.get_commit(all_shas[0])
    
    output = extractor.get_all_processed_commits()
    
    with open("test.json", "w", encoding="utf-8") as f:
        json.dump(output,f, indent = 2)