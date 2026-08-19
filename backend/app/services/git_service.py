import os
import shutil
import tempfile
import subprocess
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

try:
    from git import Repo
    HAS_GIT = True
except ImportError:
    HAS_GIT = False

ALLOWED_EXT = {".java", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".md", ".xml", ".json", ".properties", ".yaml", ".yml"}
IGNORE_DIRS = {".git", "node_modules", "target", "build", "__pycache__", ".venv", "venv", "dist", ".idea", ".vscode", "coverage", ".next", ".nuxt", "out", ".turbo", "vendor"}
IGNORE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock", "composer.lock", "Cargo.lock", "Gemfile.lock"}
MAX_FILE_BYTES = 300 * 1024

class GitService:
    def check_repository_accessible(self, url: str, timeout: int = 5) -> bool:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            res = subprocess.run(
                ["git", "ls-remote", "--exit-code", url],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            return res.returncode == 0
        except Exception:
            return False

    def clone_repository(self, url: str) -> str:
        repo_dir = tempfile.mkdtemp(prefix="repo_")
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            res = subprocess.run(
                ["git", "clone", "--depth", "1", url, repo_dir],
                capture_output=True,
                text=True,
                timeout=120,
                env=env
            )
            if res.returncode == 0:
                return repo_dir
            raise RuntimeError(
                f"git clone failed with exit code {res.returncode}: {res.stderr.strip()}"
            )
        except Exception:
            self.cleanup(repo_dir)
            raise

    def get_commit_sha(self, repo_dir: str) -> str:
        if HAS_GIT and os.path.exists(os.path.join(repo_dir, ".git")):
            try:
                git_repo = Repo(repo_dir)
                return git_repo.head.commit.hexsha
            except Exception as git_err:
                logger.debug("GitPython commit SHA resolution failed: %s", git_err)
        try:
            process_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True)
            if process_result.returncode == 0:
                return process_result.stdout.strip()
        except Exception as proc_err:
            logger.debug("subprocess git rev-parse HEAD failed: %s", proc_err)
        return "0000000000000000000000000000000000000000"

    def scan_files(self, repo_dir: str) -> List[Tuple[str, str]]:
        file_pairs = []
        for root_path, directory_names, file_names in os.walk(repo_dir):
            directory_names[:] = [dir_name for dir_name in directory_names if dir_name not in IGNORE_DIRS]
            for file_name in file_names:
                if file_name in IGNORE_FILES:
                    continue
                extension = os.path.splitext(file_name)[1].lower()
                if extension in ALLOWED_EXT:
                    absolute_path = os.path.join(root_path, file_name)
                    try:
                        if os.path.getsize(absolute_path) > MAX_FILE_BYTES:
                            continue
                    except OSError:
                        pass
                    relative_path = os.path.relpath(absolute_path, repo_dir).replace("\\", "/")
                    file_pairs.append((relative_path, absolute_path))
        return file_pairs

    def cleanup(self, repo_dir: str):
        if os.path.exists(repo_dir):
            def _remove_readonly(func, path, exc_info):
                import stat
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except Exception:
                    pass
            try:
                shutil.rmtree(repo_dir, onerror=_remove_readonly)
            except Exception as err:
                logger.debug("Failed to clean up cloned directory %s: %s", repo_dir, err)

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

