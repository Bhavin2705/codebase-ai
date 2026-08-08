import os
import shutil
import tempfile
import subprocess
from typing import List, Tuple

try:
    from git import Repo
    HAS_GIT = True
except ImportError:
    HAS_GIT = False

ALLOWED_EXT = {".java", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".md", ".xml", ".json", ".properties", ".yaml", ".yml"}
IGNORE_DIRS = {".git", "node_modules", "target", "build", "__pycache__", ".venv", "dist", ".idea"}

class GitService:
    def clone_repository(self, url: str) -> str:
        repo_dir = tempfile.mkdtemp(prefix="repo_clone_")
        if HAS_GIT:
            Repo.clone_from(url, repo_dir, depth=1)
        return repo_dir

    def get_commit_sha(self, repo_dir: str) -> str:
        if HAS_GIT and os.path.exists(os.path.join(repo_dir, ".git")):
            try:
                git_repo = Repo(repo_dir)
                return git_repo.head.commit.hexsha
            except Exception:
                pass
        try:
            process_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True)
            if process_result.returncode == 0:
                return process_result.stdout.strip()
        except Exception:
            pass
        return "0000000000000000000000000000000000000000"

    def scan_files(self, repo_dir: str) -> List[Tuple[str, str]]:
        file_pairs = []
        for root_path, directory_names, file_names in os.walk(repo_dir):
            directory_names[:] = [dir_name for dir_name in directory_names if dir_name not in IGNORE_DIRS]
            for file_name in file_names:
                extension = os.path.splitext(file_name)[1].lower()
                if extension in ALLOWED_EXT:
                    absolute_path = os.path.join(root_path, file_name)
                    relative_path = os.path.relpath(absolute_path, repo_dir).replace("\\", "/")
                    file_pairs.append((relative_path, absolute_path))
        return file_pairs

    def get_changed_files(self, repo_dir: str, base_sha: str) -> List[str]:
        if not HAS_GIT or not base_sha:
            return []
        try:
            git_repo = Repo(repo_dir)
            diff_index = git_repo.head.commit.diff(base_sha)
            changed_paths = []
            for diff_item in diff_index:
                if diff_item.b_path:
                    changed_paths.append(diff_item.b_path.replace("\\", "/"))
            return changed_paths
        except Exception:
            return []

    def cleanup(self, repo_dir: str):
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir, ignore_errors=True)

def detect_language(file_pairs: List[Tuple[str, str]]) -> str:
    extension_counts: dict[str, int] = {}
    for relative_path, _ in file_pairs:
        extension = os.path.splitext(relative_path)[1].lower()
        extension_counts[extension] = extension_counts.get(extension, 0) + 1

    js_ts_count = extension_counts.get(".js", 0) + extension_counts.get(".jsx", 0) + extension_counts.get(".ts", 0) + extension_counts.get(".tsx", 0)
    java_count = extension_counts.get(".java", 0)
    python_count = extension_counts.get(".py", 0)

    if js_ts_count > java_count and js_ts_count > python_count:
        return "JavaScript / React / Node"
    if java_count >= python_count and java_count > 0:
        return "Java / Spring Boot"
    if python_count > 0:
        return "Python"
    return "Multi-Language"

