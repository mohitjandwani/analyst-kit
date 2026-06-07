#!/usr/bin/env python3
"""
Git synchronization utilities for company universe manager.
Handles pull, commit, and push operations with conflict detection.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run shell command and return output."""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def ensure_repo_exists(repo_path):
    """Check if repository exists and is a git repo."""
    if not os.path.exists(repo_path):
        return False, f"Repository path does not exist: {repo_path}"
    
    git_dir = os.path.join(repo_path, ".git")
    if not os.path.exists(git_dir):
        return False, f"Not a git repository: {repo_path}"
    
    return True, "Repository exists"


def git_pull(repo_path):
    """Pull latest changes from remote."""
    code, stdout, stderr = run_command("git pull origin main", cwd=repo_path)
    
    if code != 0:
        return False, f"Git pull failed: {stderr}"
    
    if "CONFLICT" in stdout or "CONFLICT" in stderr:
        return False, f"Merge conflict detected. Please resolve manually.\n{stdout}"
    
    return True, stdout


def git_status(repo_path):
    """Get git status."""
    code, stdout, stderr = run_command("git status --porcelain", cwd=repo_path)
    
    if code != 0:
        return False, f"Git status failed: {stderr}"
    
    return True, stdout


def git_commit_and_push(repo_path, file_path, message):
    """Commit specific file and push to remote."""
    # Add file
    code, stdout, stderr = run_command(f"git add {file_path}", cwd=repo_path)
    if code != 0:
        return False, f"Git add failed: {stderr}"
    
    # Commit
    code, stdout, stderr = run_command(f'git commit -m "{message}"', cwd=repo_path)
    if code != 0:
        # Check if it's just "nothing to commit"
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            return True, "No changes to commit"
        return False, f"Git commit failed: {stderr}"
    
    # Push
    code, stdout, stderr = run_command("git push origin main", cwd=repo_path)
    if code != 0:
        return False, f"Git push failed: {stderr}"
    
    return True, "Changes committed and pushed successfully"


def main():
    """Command-line interface."""
    if len(sys.argv) < 3:
        print("Usage:")
        print("  git_sync.py pull <repo_path>")
        print("  git_sync.py commit <repo_path> <file_path> <message>")
        sys.exit(1)
    
    action = sys.argv[1]
    repo_path = sys.argv[2]
    
    # Ensure repo exists
    success, msg = ensure_repo_exists(repo_path)
    if not success:
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)
    
    if action == "pull":
        success, msg = git_pull(repo_path)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "commit":
        if len(sys.argv) < 5:
            print("ERROR: commit requires <file_path> and <message>", file=sys.stderr)
            sys.exit(1)
        
        file_path = sys.argv[3]
        message = sys.argv[4]
        
        success, msg = git_commit_and_push(repo_path, file_path, message)
        print(msg)
        sys.exit(0 if success else 1)
    
    elif action == "status":
        success, msg = git_status(repo_path)
        print(msg)
        sys.exit(0 if success else 1)
    
    else:
        print(f"ERROR: Unknown action '{action}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
