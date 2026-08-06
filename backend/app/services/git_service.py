import os
import shutil
import tempfile
from typing import List, Tuple
try:
    from git import Repo
    HAS_GIT = True
except ImportError:
    HAS_GIT = False

ALLOWED_EXTENSIONS = {".java", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".md", ".xml", ".json", ".properties", ".yaml", ".yml"}
IGNORE_DIRS = {".git", "node_modules", "target", "build", "__pycache__", ".venv", "dist", ".idea"}

class GitService:
    def clone_repository(self, github_url: str) -> str:
        temp_directory = tempfile.mkdtemp(prefix="repo_clone_")
        if HAS_GIT:
            Repo.clone_from(github_url, temp_directory, depth=1)
        return temp_directory

    def scan_files(self, repository_directory: str) -> List[Tuple[str, str]]:
        scanned_file_pairs = []
        for root, directories, files in os.walk(repository_directory):
            directories[:] = [d for d in directories if d not in IGNORE_DIRS]
            for file_name in files:
                file_extension = os.path.splitext(file_name)[1].lower()
                if file_extension in ALLOWED_EXTENSIONS:
                    absolute_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(absolute_path, repository_directory).replace("\\", "/")
                    scanned_file_pairs.append((relative_path, absolute_path))
        return scanned_file_pairs

    def cleanup(self, repository_directory: str):
        if os.path.exists(repository_directory):
            shutil.rmtree(repository_directory, ignore_errors=True)

