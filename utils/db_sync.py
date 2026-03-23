"""
Auto-backup: pushes hiring.db to GitHub (db-backup branch) after every write.
Auto-restore: pulls from GitHub on startup if the local DB is empty/fresh.

Uses GitHub Contents API — no extra libraries needed (stdlib urllib only).
Token is read from st.secrets or env var GITHUB_TOKEN.
"""

import os
import base64
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
GITHUB_REPO  = "anileeanimation-hash/anilee-hiring"
GITHUB_BRANCH = "db-backup"
GITHUB_FILE   = "hiring.db"
API_BASE      = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"

# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_token() -> str:
    """Read GitHub PAT from st.secrets → env var → hardcoded fallback."""
    try:
        import streamlit as st
        tok = st.secrets.get("GITHUB_TOKEN", "")
        if tok:
            return tok
    except Exception:
        pass
    return os.environ.get("GITHUB_TOKEN", "")


def _api_request(method: str, url: str, token: str, body: dict = None):
    """Make a GitHub API call. Returns (response_dict, error_str)."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
        "User-Agent": "AnileeHiringPortal/1.0",
    }
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
            return None, f"HTTP {e.code}: {err_body.get('message', str(e))}"
        except Exception:
            return None, f"HTTP {e.code}: {e.reason}"
    except Exception as ex:
        return None, str(ex)


def _get_remote_sha(token: str):
    """Get the current SHA of the file on GitHub (needed to update it). Returns (sha, error)."""
    url = f"{API_BASE}?ref={GITHUB_BRANCH}"
    result, err = _api_request("GET", url, token)
    if err:
        return None, err
    return result.get("sha"), None


# ── Public API ────────────────────────────────────────────────────────────────

def push_db(db_path: str, reason: str = "auto-backup") -> tuple[bool, str]:
    """
    Push the SQLite DB file to GitHub as base64.
    Returns (success: bool, message: str).
    """
    token = _get_token()
    if not token:
        return False, "GITHUB_TOKEN not configured"

    if not os.path.exists(db_path):
        return False, f"DB file not found: {db_path}"

    try:
        with open(db_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return False, f"Could not read DB: {e}"

    # Get current SHA (needed to update existing file)
    sha, err = _get_remote_sha(token)
    # If err and NOT a 404, something is wrong
    if err and "404" not in err and "Not Found" not in err:
        return False, f"Could not get remote SHA: {err}"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = {
        "message": f"[auto-backup] {reason} — {timestamp}",
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        body["sha"] = sha

    result, err = _api_request("PUT", API_BASE, token, body)
    if err:
        return False, f"Push failed: {err}"

    return True, f"Backed up to GitHub at {timestamp}"


def pull_db(db_path: str) -> tuple[bool, str]:
    """
    Pull DB from GitHub and write to db_path.
    Returns (success: bool, message: str).
    Only restores if remote file exists and has content.
    """
    token = _get_token()
    if not token:
        return False, "GITHUB_TOKEN not configured"

    url = f"{API_BASE}?ref={GITHUB_BRANCH}"
    result, err = _api_request("GET", url, token)
    if err:
        if "404" in err or "Not Found" in err:
            return False, "No backup found on GitHub yet"
        return False, f"Pull failed: {err}"

    content_b64 = result.get("content", "").replace("\n", "")
    if not content_b64:
        return False, "Remote file is empty"

    try:
        db_bytes = base64.b64decode(content_b64)
    except Exception as e:
        return False, f"Base64 decode error: {e}"

    # Sanity check: SQLite files start with "SQLite format 3"
    if not db_bytes[:16].startswith(b"SQLite format 3"):
        return False, "Remote file does not appear to be a valid SQLite database"

    try:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        with open(db_path, "wb") as f:
            f.write(db_bytes)
    except Exception as e:
        return False, f"Could not write DB: {e}"

    size_kb = len(db_bytes) // 1024
    return True, f"Restored from GitHub ({size_kb} KB)"


def ensure_db_branch_exists():
    """
    Create the db-backup branch on GitHub if it doesn't exist yet.
    Called once on first push; safe to call multiple times.
    """
    token = _get_token()
    if not token:
        return False, "GITHUB_TOKEN not configured"

    # Get main branch SHA
    ref_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/refs/heads/main"
    result, err = _api_request("GET", ref_url, token)
    if err:
        # try 'master'
        ref_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/refs/heads/master"
        result, err = _api_request("GET", ref_url, token)
        if err:
            return False, f"Could not find main/master branch: {err}"

    base_sha = result.get("object", {}).get("sha", "")
    if not base_sha:
        return False, "Could not get base branch SHA"

    # Check if db-backup already exists
    check_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/refs/heads/{GITHUB_BRANCH}"
    check, _ = _api_request("GET", check_url, token)
    if check:
        return True, f"Branch '{GITHUB_BRANCH}' already exists"

    # Create the branch
    create_url = f"https://api.github.com/repos/{GITHUB_REPO}/git/refs"
    body = {"ref": f"refs/heads/{GITHUB_BRANCH}", "sha": base_sha}
    _, err = _api_request("POST", create_url, token, body)
    if err and "already exists" not in err.lower():
        return False, f"Could not create branch: {err}"

    return True, f"Created branch '{GITHUB_BRANCH}'"


# ── Background push helper ────────────────────────────────────────────────────

def trigger_backup_async(db_path: str, reason: str = "data entry"):
    """
    Fire-and-forget: push DB to GitHub in a background thread.
    Does not block the UI.
    """
    def _worker():
        try:
            ok, msg = push_db(db_path, reason)
            if not ok:
                # Silently log — don't crash the app
                pass
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
