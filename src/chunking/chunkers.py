"""Checkpoint 4: two chunking strategies for the vector store.

per_commit : one chunk per commit (the CP3 behaviour, uses parse_commit's embedding_text).
per_file   : one chunk per changed file in each commit. Every chunk repeats the commit
             header (message/date) so it still makes sense on its own, then holds the
             diff of just that one file. Large commits no longer get squeezed into a
             single vector, and the 5-file / 15-line cap from CP3 no longer hides files.

Both return dicts shaped for CommitVectorStore: {"sha": <unique chunk id>,
"commit_sha": <real commit sha>, "embedding_text": <text to embed>}.
Search results are mapped back to commits through "commit_sha".
"""
import re
from typing import Dict, List

SKIP_FILES = re.compile(r"(\.lock|package-lock\.json|\.svg|\.min\.js|\.gif|\.png|\.jpe?g)$")
PER_FILE_MAX_LINES = 40


def _sanitize(patch: str, max_lines: int) -> List[str]:
    out = []
    for line in patch.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith(("+", "-")) and line[1:].strip():
            out.append(line[0] + " " + line[1:].strip())
            if len(out) >= max_lines:
                break
    return out


def per_commit_chunks(parsed_commits: List[Dict]) -> List[Dict]:
    return [
        {"sha": c["sha"], "commit_sha": c["sha"], "embedding_text": c["embedding_text"]}
        for c in parsed_commits
    ]


def per_file_chunks(raw_commits: List[Dict], max_lines: int = PER_FILE_MAX_LINES) -> List[Dict]:
    chunks = []
    for raw in raw_commits:
        sha = raw["sha"]
        info = raw.get("commit", {})
        message = info.get("message", "").strip()
        date = info.get("author", {}).get("date", "")
        header = f"Commit: {sha[:7]}\nDate: {date}\nMessage: {message}\n"

        file_chunks = []
        for f in raw.get("files", []):
            filename = f.get("filename", "")
            if SKIP_FILES.search(filename):
                continue
            diff = _sanitize(f.get("patch", "") or "", max_lines)
            text = (f"{header}File: {filename} (+{f.get('additions', 0)}, -{f.get('deletions', 0)})\n"
                    + "\n".join(diff))
            file_chunks.append({"sha": f"{sha}:{filename}", "commit_sha": sha, "embedding_text": text})

        if not file_chunks:  # keep commits with no usable diff searchable by their message
            file_chunks.append({"sha": f"{sha}:_message", "commit_sha": sha, "embedding_text": header})
        chunks.extend(file_chunks)
    return chunks


CHUNKERS = {"per_commit", "per_file"}
