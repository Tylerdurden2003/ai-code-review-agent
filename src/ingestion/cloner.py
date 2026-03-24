import os
import shutil
import stat
import tempfile
from git import Repo


def clone_repo(github_url: str) -> str:
    """
    Clones a GitHub repo into a temporary directory.
    Returns the path to the cloned repo.
    """
    tmp_dir = tempfile.mkdtemp()
    print(f"Cloning {github_url} into {tmp_dir}...")
    Repo.clone_from(github_url, tmp_dir)
    return tmp_dir


def cleanup_repo(repo_path: str):
    if os.path.exists(repo_path):
        # Windows fix: remove read-only flags before deleting
        def handle_remove_readonly(func, path, exc):
            os.chmod(path, stat.S_IWRITE)
            func(path)

        shutil.rmtree(repo_path, onerror=handle_remove_readonly)
        print(f"Cleaned up {repo_path}")
