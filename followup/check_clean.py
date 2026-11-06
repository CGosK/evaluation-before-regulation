"""
Check a tree before it goes public: no home paths, usernames, personal emails, keys or plan-window readings.

    text files   home paths (/Users/<name>, /home/<name>, C:\\Users), the local username, email addresses
                 other than GitHub and Anthropic noreply ones, and key-like strings
    data files   (.json, .jsonl, .txt, .log, .csv) also plan-window fields: utilization, resets_at,
                 overage, pauses
    binary files home paths and the local username, as raw bytes
    any file     anything under followup/private/

Usage:  .venv/bin/python followup/check_clean.py DIR [--user NAME]
Exits 1 and lists each hit if anything is found.
"""

import argparse
import getpass
import re
import sys
from pathlib import Path

HOME = re.compile(r"/Users/[A-Za-z][\w.-]*|/home/[a-z][\w.-]*|[A-Z]:\\\\?Users\\\\?\w+")
EMAIL = re.compile(r"[\w.+-]+@[A-Za-z][\w-]*(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")
ALLOWED_EMAIL = re.compile(
    r"@users\.noreply\.github\.com$|^noreply@anthropic\.com$|@example\.(com|org)$"
)
KEY = re.compile(r"sk-ant-[\w-]{8,}|sk-[A-Za-z0-9]{32,}|ghp_\w{20,}|AKIA[0-9A-Z]{16}|hf_\w{20,}")
PLAN = re.compile(
    r"\"(utilization|weekly_utilization|resets_at|weekly_resets_at|using_overage|isUsingOverage|"
    r"paused_until)\""
)
DATA = {".json", ".jsonl", ".txt", ".log", ".csv"}
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}


def scan(root: Path, user: str) -> list:
    hits = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or SKIP_DIRS & set(f.relative_to(root).parts):
            continue
        raw = f.read_bytes()
        rel = f.relative_to(root)
        if rel.parts[:2] == ("followup", "private"):
            hits.append((rel, "private file", str(rel)))
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            for needle in (b"/Users/", f"/home/{user}".encode(), user.encode()):
                if needle in raw:
                    hits.append((rel, "binary", needle.decode()))
            continue
        for kind, rx in (("home path", HOME), ("key", KEY)):
            hits += [(rel, kind, m.group(0)) for m in rx.finditer(text)]
        if user and user in text:
            hits.append((rel, "username", user))
        hits += [
            (rel, "email", m.group(0))
            for m in EMAIL.finditer(text)
            if not ALLOWED_EMAIL.search(m.group(0))
        ]
        if f.suffix in DATA:
            hits += [(rel, "plan reading", m.group(1)) for m in PLAN.finditer(text)]
    return hits


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root", type=Path)
    ap.add_argument("--user", default=getpass.getuser())
    a = ap.parse_args()
    hits = scan(a.root, a.user)
    seen = {}
    for rel, kind, what in hits:
        seen.setdefault((str(rel), kind), what)
    for (rel, kind), what in seen.items():
        print(f"{kind}: {rel}: {what[:80]}")
    print(f"{len(seen)} file-and-kind hits in {a.root}" if seen else f"clean: {a.root}")
    sys.exit(1 if seen else 0)
