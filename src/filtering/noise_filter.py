"""Checkpoint 4: commit pre-filtering (noise removal) before embedding.

Each rule returns a short reason string when a commit is noise, or None to keep it.
Rules run in order and the first match wins, so the "dropped" log shows exactly
why each commit was removed (this log is saved as evidence by the benchmark).

The rules are intentionally conservative: a commit is only dropped when it cannot
contain a release-worthy change on its own.
"""
import re
from typing import Dict, List, Optional, Tuple

VERSION_FILES = re.compile(r"(^|/)(_?version\.py|VERSION|version\.txt)$")
ASSET_FILES = re.compile(r"\.(gif|png|jpe?g|svg|ico|lock)$|package-lock\.json$")
TRIVIAL_MSG = re.compile(
    r"\b(typo|typos|whitespace|formatting|flake8|pep8|lint|oops|"
    r"badge|badges|minor doc|minor documentation)\b",
    re.IGNORECASE,
)
TRIVIAL_MAX_LINES = 10  # a "trivial" message only drops the commit if the diff is also small


def _lines_changed(raw: Dict) -> int:
    return sum(f.get("additions", 0) + f.get("deletions", 0) for f in raw.get("files", []))


def rule_merge(raw: Dict) -> Optional[str]:
    # Merge commits repeat the diffs of the branch commits they merge, which are
    # already indexed individually. Keeping them double-counts the same change.
    if len(raw.get("parents", [])) > 1:
        return "merge commit (content already in branch commits)"
    return None


def rule_empty(raw: Dict) -> Optional[str]:
    if not raw.get("files"):
        return "no file changes"
    return None


def rule_version_only(raw: Dict) -> Optional[str]:
    files = [f["filename"] for f in raw.get("files", [])]
    if files and all(VERSION_FILES.search(fn) for fn in files):
        return "version bump only"
    return None


def rule_assets_only(raw: Dict) -> Optional[str]:
    files = [f["filename"] for f in raw.get("files", [])]
    if files and all(ASSET_FILES.search(fn) for fn in files):
        return "binary/asset files only"
    return None


MULTI_PURPOSE = re.compile(r",|;| \+ | and ")


def rule_trivial(raw: Dict) -> Optional[str]:
    # v1 of this rule dropped "fix flake8, preformance test overhead threshold ..." (a real
    # perf-test change) -- the retrieval benchmark's safety check caught it. A message that lists
    # several changes ("x, y" / "x + y" / "x and y") is now never treated as trivial.
    message = raw.get("commit", {}).get("message", "")
    first_line = message.splitlines()[0] if message else ""
    if MULTI_PURPOSE.search(first_line):
        return None
    if TRIVIAL_MSG.search(first_line) and _lines_changed(raw) <= TRIVIAL_MAX_LINES:
        return f"trivial change ('{first_line[:50]}', <= {TRIVIAL_MAX_LINES} lines)"
    return None


RULES = [rule_merge, rule_empty, rule_version_only, rule_assets_only, rule_trivial]


def filter_commits(raw_commits: List[Dict], keep_shas: Tuple[str, ...] = ()) -> Tuple[List[Dict], List[Dict]]:
    """Split raw GitHub commit JSON into (kept, dropped).

    keep_shas: commits that must never be dropped (e.g. first/last commit of the range).
    dropped entries are {"sha", "message", "reason"}.
    """
    kept, dropped = [], []
    for raw in raw_commits:
        reason = None
        if raw["sha"] not in keep_shas:
            for rule in RULES:
                reason = rule(raw)
                if reason:
                    break
        if reason:
            msg = raw.get("commit", {}).get("message", "").splitlines()
            dropped.append({"sha": raw["sha"][:7], "message": msg[0] if msg else "", "reason": reason})
        else:
            kept.append(raw)
    return kept, dropped
