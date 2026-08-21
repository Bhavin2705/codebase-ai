import logging
import re
import uuid
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File as FileModel
from app.models.repository import Repository
from app.models.symbol import Symbol as SymbolModel
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

# --- Retrieval Configuration & Constants ---

DEFAULT_STOPWORDS: Set[str] = {
    "what", "how", "does", "the", "and", "for", "this", "repo", "repository",
    "workspace", "project", "where", "are", "code", "explain", "about", "is",
    "a", "an", "in", "of", "to", "me", "when", "asks", "keep", "your", "response",
    "precise", "tell", "show", "can", "you", "please", "i", "site", "website",
    "class", "classes", "entity", "entities", "method", "methods", "function",
    "functions", "interface", "interfaces", "file", "files", "package", "packages",
    "module", "modules", "defined", "located", "handles", "handled", "handling",
    "represents", "providing", "fields"
}

FLOW_QUERY_KEYWORDS = [
    "flow", "trace", "lifecycle", "auth", "authentication", "login", "register",
    "routing", "middleware", "request", "response", "pipeline", "handle", "handling",
    "process", "processing", "endpoint", "architecture", "execution"
]

OVERVIEW_QUERY_PATTERNS = [
    "what is this repo about", "repo about", "repository about", "overview", "what does this repo do",
    "architecture", "explain repo", "explain repository", "project structure", "readme",
    "workspace", "workspace about", "what is this workspace about", "project about", "explain project",
    "explain workspace", "what is this project about", "what does this project do", "summary", "about this",
    "flow of request", "request flow", "flow of the request", "how request works", "request processing"
]

STRUCTURAL_FILE_PATTERNS = [
    "%package.json", "%readme.md", "%readme", "%app.js", "%server.js",
    "%main.jsx", "%app.jsx", "%main.tsx", "%app.tsx", "%main.js",
    "%requirements.txt", "%pom.xml", "%build.gradle", "%go.mod", "%cargo.toml"
]

MANIFEST_FILES = {
    "package.json", "requirements.txt", "pom.xml",
    "build.gradle", "go.mod", "cargo.toml"
}
README_FILES = {"readme.md", "readme", "readme.txt"}
SERVER_ENTRY_FILES = {
    "app.js", "server.js", "main.py", "app.py", "application.java", "main.go"
}
CLIENT_ENTRY_FILES = {
    "app.jsx", "main.jsx", "app.tsx", "main.tsx", "main.js", "index.html"
}
PRIMARY_ENTRY_SYMBOLS = {
    "App", "createApp", "main", "package.json", "README.md", "main.jsx"
}

DUMMY_ASSET_PENALTY = -200


class RetrievalService:
    """
    Hybrid semantic (pgvector) and lexical (exact symbol/file matches) code retrieval engine.
    """

    def __init__(self, embedder: EmbeddingService = None):
        self.embedder = embedder or EmbeddingService()

    @staticmethod
    def _extract_query_terms(query_text: str) -> List[str]:
        tokens = set(re.findall(r"[A-Za-z0-9_]+", query_text.lower()))
        return [t for t in tokens if t not in DEFAULT_STOPWORDS and len(t) >= 2]

    @staticmethod
    def _detect_query_intent(query_text: str) -> Tuple[bool, bool]:
        q_lower = query_text.lower()
        is_flow = any(k in q_lower for k in FLOW_QUERY_KEYWORDS)
        is_overview = any(p in q_lower for p in OVERVIEW_QUERY_PATTERNS)
        return is_flow, is_overview

    async def _resolve_repository(
        self, repository_id: str, db: AsyncSession
    ) -> Tuple[Repository | None, Dict[str, Any]]:
        repo = None
        try:
            repo_uuid = uuid.UUID(repository_id)
            stmt = select(Repository).where(Repository.id == repo_uuid)
            repo = (await db.execute(stmt)).scalars().first()
        except ValueError:
            stmt = select(Repository).where(Repository.name.ilike(f"%{repository_id}%"))
            repo = (await db.execute(stmt)).scalars().first()

        repo_meta = {
            "name": repo.name if repo else "Workspace",
            "language": repo.language if repo else "Multi-Language",
            "total_files": 0,
            "all_files": [],
        }

        if not repo:
            return None, repo_meta

        stmt_paths = (
            select(FileModel.path)
            .where(FileModel.repository_id == repo.id)
            .order_by(FileModel.path)
        )
        all_file_paths: List[str] = list((await db.execute(stmt_paths)).scalars().all())
        repo_meta["all_files"] = all_file_paths
        repo_meta["total_files"] = len(all_file_paths)
        return repo, repo_meta

    async def _fetch_structural_candidates(
        self, repo_id: uuid.UUID, db: AsyncSession, candidates: Dict[uuid.UUID, Dict[str, Any]]
    ) -> None:
        struct_conditions = [FileModel.path.ilike(p) for p in STRUCTURAL_FILE_PATTERNS]
        stmt_struct = (
            select(SymbolModel, FileModel)
            .join(FileModel, SymbolModel.file_id == FileModel.id)
            .where(
                FileModel.repository_id == repo_id,
                or_(*struct_conditions)
            )
        )
        struct_rows = (await db.execute(stmt_struct)).all()
        for sym, file_rec in struct_rows:
            candidates[sym.id] = {
                "sym": sym,
                "file": file_rec,
                "vec_score": 0.0,
                "is_structural": True,
            }

    async def _fetch_vector_candidates(
        self,
        repo_id: uuid.UUID,
        q_vec: List[float],
        top_k: int,
        db: AsyncSession,
        candidates: Dict[uuid.UUID, Dict[str, Any]],
    ) -> None:
        if not q_vec:
            return
        try:
            cos_dist = SymbolModel.embedding.cosine_distance(q_vec)
            stmt_vector = (
                select(SymbolModel, FileModel, cos_dist.label("dist"))
                .join(FileModel, SymbolModel.file_id == FileModel.id)
                .where(
                    FileModel.repository_id == repo_id,
                    SymbolModel.embedding.is_not(None)
                )
                .order_by(cos_dist)
                .limit(top_k * 4)
            )
            vec_rows = (await db.execute(stmt_vector)).all()
            for sym, file_rec, dist in vec_rows:
                vec_score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
                if sym.id in candidates:
                    candidates[sym.id]["vec_score"] = vec_score
                else:
                    candidates[sym.id] = {
                        "sym": sym,
                        "file": file_rec,
                        "vec_score": vec_score,
                        "is_structural": False,
                    }
        except Exception as err:
            logger.debug("Vector candidate search skipped or failed: %s", err)

    async def _fetch_lexical_candidates(
        self,
        repo_id: uuid.UUID,
        query_terms: List[str],
        top_k: int,
        db: AsyncSession,
        candidates: Dict[uuid.UUID, Dict[str, Any]],
    ) -> None:
        if not query_terms:
            return
        lex_conditions = []
        for t in query_terms[:5]:
            pattern = f"%{t}%"
            lex_conditions.append(FileModel.path.ilike(pattern))
            lex_conditions.append(SymbolModel.name.ilike(pattern))
            lex_conditions.append(SymbolModel.signature.ilike(pattern))

        stmt_lex = (
            select(SymbolModel, FileModel)
            .join(FileModel, SymbolModel.file_id == FileModel.id)
            .where(
                FileModel.repository_id == repo_id,
                or_(*lex_conditions)
            )
            .limit(top_k * 4)
        )
        lex_rows = (await db.execute(stmt_lex)).all()
        for sym, file_rec in lex_rows:
            if sym.id not in candidates:
                candidates[sym.id] = {
                    "sym": sym,
                    "file": file_rec,
                    "vec_score": 0.0,
                    "is_structural": False,
                }

    async def _fetch_fallback_candidates(
        self,
        repo_id: uuid.UUID,
        top_k: int,
        db: AsyncSession,
        candidates: Dict[uuid.UUID, Dict[str, Any]],
    ) -> None:
        if candidates:
            return
        stmt_fallback = (
            select(SymbolModel, FileModel)
            .join(FileModel, SymbolModel.file_id == FileModel.id)
            .where(FileModel.repository_id == repo_id)
            .limit(top_k * 2)
        )
        fallback_rows = (await db.execute(stmt_fallback)).all()
        for sym, file_rec in fallback_rows:
            candidates[sym.id] = {
                "sym": sym,
                "file": file_rec,
                "vec_score": 0.0,
                "is_structural": False,
            }

    @staticmethod
    def _score_candidates(
        candidates: Dict[uuid.UUID, Dict[str, Any]],
        query_terms: List[str],
        is_overview: bool,
    ) -> List[Dict[str, Any]]:
        scored = []
        for cdata in candidates.values():
            sym = cdata["sym"]
            file_rec = cdata["file"]
            vec_score = cdata["vec_score"]
            is_struct = cdata.get("is_structural", False)

            file_path = file_rec.path
            path_lower = file_path.lower()
            sym_name_lower = sym.name.lower()
            filename_only = path_lower.split("/")[-1]
            fn_stem = filename_only.rsplit(".", 1)[0]

            lex_score = 0
            for term in query_terms:
                if term == filename_only or term == fn_stem:
                    lex_score += 60
                elif term in filename_only or (len(fn_stem) >= 3 and fn_stem in term):
                    lex_score += 40
                elif term in path_lower:
                    lex_score += 15
                if term in sym_name_lower or (len(sym_name_lower) >= 3 and sym_name_lower in term):
                    lex_score += 35

            # Overview structural bonus with prioritized tiers
            struct_bonus = 0
            if is_overview:
                if filename_only in MANIFEST_FILES:
                    struct_bonus = 1000
                elif filename_only in README_FILES:
                    struct_bonus = 900
                elif filename_only in SERVER_ENTRY_FILES:
                    struct_bonus = 800
                elif filename_only in CLIENT_ENTRY_FILES:
                    struct_bonus = 700
                elif is_struct:
                    struct_bonus = 500

                if sym.start_line == 1 or sym.name in PRIMARY_ENTRY_SYMBOLS:
                    struct_bonus += 50

            # Suppress synthetic test assets when indexing real code
            if "dummy" in path_lower or "test_assets" in path_lower or "dummy_assets" in path_lower:
                lex_score += DUMMY_ASSET_PENALTY

            total_score = (vec_score * 100.0) + lex_score + struct_bonus
            start_l = sym.start_line or 1
            end_l = sym.end_line or start_l

            if sym.source_code:
                source_code = sym.source_code
            elif file_rec.content:
                lines = file_rec.content.splitlines()
                source_code = "\n".join(lines[max(0, start_l - 1) : end_l])
            else:
                source_code = ""

            scored.append({
                "score": total_score,
                "file_path": file_path,
                "context": {
                    "name": sym.name,
                    "file_path": file_path,
                    "signature": sym.signature or f"file {file_path}",
                    "start_line": start_l,
                    "end_line": end_l,
                    "source_code": source_code,
                }
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    @staticmethod
    def _select_diverse_contexts(
        scored: List[Dict[str, Any]],
        is_overview: bool,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        limit = 5 if is_overview else top_k
        max_per_file = 1 if is_overview else 2

        contexts = []
        file_counts: Dict[str, int] = {}
        deferred = []

        for item in scored:
            fpath = item["file_path"]
            if file_counts.get(fpath, 0) < max_per_file:
                contexts.append(item["context"])
                file_counts[fpath] = file_counts.get(fpath, 0) + 1
                if len(contexts) >= limit:
                    break
            else:
                deferred.append(item["context"])

        if len(contexts) < limit:
            for ctx in deferred:
                contexts.append(ctx)
                if len(contexts) >= limit:
                    break

        return contexts

    async def retrieve_contexts(
        self,
        question: str,
        repository_id: str,
        db: AsyncSession,
        top_k: int = 8,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        repo, repo_meta = await self._resolve_repository(repository_id, db)
        if not repo:
            return [], repo_meta

        q_vec = []
        try:
            q_vec = await self.embedder.generate_embedding(question, input_type="query")
        except Exception as err:
            logger.debug("Failed generating query vector: %s", err)

        query_terms = self._extract_query_terms(question)
        _, is_overview = self._detect_query_intent(question)

        candidates: Dict[uuid.UUID, Dict[str, Any]] = {}

        if is_overview:
            await self._fetch_structural_candidates(repo.id, db, candidates)

        await self._fetch_vector_candidates(repo.id, q_vec, top_k, db, candidates)
        await self._fetch_lexical_candidates(repo.id, query_terms, top_k, db, candidates)
        await self._fetch_fallback_candidates(repo.id, top_k, db, candidates)

        scored = self._score_candidates(candidates, query_terms, is_overview)
        contexts = self._select_diverse_contexts(scored, is_overview, top_k)

        return contexts, repo_meta


retrieval_service = RetrievalService()
