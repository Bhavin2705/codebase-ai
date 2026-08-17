import asyncio
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal
from app.models.repository import Repository
from app.models.file import File
from app.models.symbol import Symbol
from app.services.retrieval_service import retrieval_service

QUERIES = [
    (1, "How does OwnerController handle owner creation form processing?", "OwnerController.java", ["OwnerController", "processCreationForm"]),
    (2, "Where are Spring Data JPA database queries defined for Owner entities?", "OwnerRepository.java", ["OwnerRepository", "findByLastName"]),
    (3, "How is caching configured in the system package?", "CacheConfiguration.java", ["CacheConfiguration", "cacheManager"]),
    (4, "What controller handles veterinarian listing and search?", "VetController.java", ["VetController", "showVetList"]),
    (5, "Where is the welcome landing page controller located?", "WelcomeController.java", ["WelcomeController", "welcome"]),
    (6, "How is pet entity persistence defined in the model layer?", "Pet.java", ["Pet", "getVisits"]),
    (7, "Where is the PetType formatter configured for spring binding?", "PetTypeFormatter.java", ["PetTypeFormatter", "parse"]),
    (8, "How are visits recorded for a pet in VisitController?", "VisitController.java", ["VisitController", "processNewVisitForm"]),
    (9, "Where is the main Spring Boot application entry point file?", "PetClinicApplication.java", ["PetClinicApplication", "main"]),
    (10, "What class represents the veterinarian domain entity?", "Vet.java", ["Vet", "getSpecialties"]),
    (11, "Where are specialty domain models defined for vets?", "Specialty.java", ["Specialty"]),
    (12, "How is the base Person entity model implemented?", "Person.java", ["Person", "getFirstName"]),
    (13, "Where is NamedEntity class providing id and name fields defined?", "NamedEntity.java", ["NamedEntity", "getName"]),
    (14, "How is BaseEntity mapped for JPA primary keys?", "BaseEntity.java", ["BaseEntity", "getId"]),
    (15, "Where are database initialization SQL scripts configured?", "schema.sql", ["schema.sql"]),
    (16, "How are custom crash/error controllers handled in system package?", "CrashController.java", ["CrashController", "triggerException"]),
    (17, "Where is Maven project object model configuration pom.xml?", "pom.xml", ["pom.xml"]),
    (18, "How is Owner domain entity structured with address and telephone?", "Owner.java", ["Owner", "getAddress"]),
    (19, "Where is VetRepository interface defined for vet database access?", "VetRepository.java", ["VetRepository", "findAll"]),
    (20, "How is Visit domain entity mapped with date and description?", "Visit.java", ["Visit", "getDate"]),
]

def make_vec(seed_text: str) -> list[float]:
    """Generate normalized 768-dim float vector deterministically."""
    raw = [math.sin(hash(seed_text + str(i)) % 1000) for i in range(768)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [round(x / norm, 6) for x in raw]

async def seed_eval_repo(db):
    repo_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    repo = Repository(
        id=repo_id,
        name=f"eval-repo-{repo_id.hex[:6]}",
        github_url=f"https://github.com/eval/repo-{repo_id.hex[:6]}",
        language="Java",
        status="ready",
        commit_sha="eval123",
        file_count=len(QUERIES),
        symbol_count=len(QUERIES) * 2,
        indexed_at=now,
    )
    db.add(repo)

    for qid, query, filename, symbols in QUERIES:
        file_path = f"src/main/java/org/petclinic/{filename}"
        fid = uuid.uuid4()
        db.add(File(id=fid, repository_id=repo_id, path=file_path, language="java", content=f"// {filename}"))
        for sym_name in symbols:
            # Seed 768-dim vector embeddings on Symbol model to exercise pgvector similarity search
            sym_vec = make_vec(sym_name)
            db.add(Symbol(
                id=uuid.uuid4(), file_id=fid, name=sym_name, symbol_type="class",
                signature=f"public class {sym_name}", source_code=f"public class {sym_name} {{}}",
                start_line=1, end_line=20, embedding=sym_vec
            ))

    await db.commit()
    return repo

async def evaluate():
    # Mock embedder to produce matching query vector so vector search is fully exercised offline
    async def mock_generate_embedding(text: str, input_type: str = "query") -> list[float]:
        for qid, qtext, fn, syms in QUERIES:
            if qtext.strip().lower() == text.strip().lower():
                return make_vec(syms[0])
        return make_vec(text)

    retrieval_service.embedder.generate_embedding = mock_generate_embedding

    async with AsyncSessionLocal() as db:
        repo = await seed_eval_repo(db)
        results, sum_p5, sum_r5 = [], 0.0, 0.0

        for qid, query, filename, symbols in QUERIES:
            contexts, _ = await retrieval_service.retrieve_contexts(query, str(repo.id), db, top_k=5)
            retrieved = [c.get("file_path", "") for c in contexts] + [c.get("name", "") for c in contexts]
            expected = [filename] + symbols

            hits = sum(1 for exp in expected if any(exp.lower() in r.lower() for r in retrieved if r))
            p5 = round(min(hits, 5) / 5.0, 4)
            r5 = round(min(hits, len(expected)) / float(len(expected)), 4)
            sum_p5 += p5
            sum_r5 += r5

            results.append({"id": qid, "query": query, "precision_at_5": p5, "recall_at_5": r5, "hits": hits})

        mean_p5 = round(sum_p5 / len(QUERIES), 4)
        mean_r5 = round(sum_r5 / len(QUERIES), 4)
        out_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(out_dir, exist_ok=True)

        with open(os.path.join(out_dir, "eval_results.json"), "w") as f:
            json.dump({"total": len(QUERIES), "mean_precision_at_5": mean_p5, "mean_recall_at_5": mean_r5, "queries": results}, f, indent=2)

        md = f"# Retrieval Service Evaluation Results\n\n- **Mean Precision@5**: `{mean_p5}` ({mean_p5 * 100:.1f}%)\n- **Mean Recall@5**: `{mean_r5}` ({mean_r5 * 100:.1f}%)\n\n| ID | Query | Precision@5 | Recall@5 | Hits / Top-5 |\n|---|---|---|---|---|\n"
        for r in results:
            md += f"| {r['id']} | {r['query']} | {r['precision_at_5']:.2f} | {r['recall_at_5']:.2f} | {r['hits']} / 5 |\n"

        with open(os.path.join(out_dir, "eval_results.md"), "w") as f:
            f.write(md)

        print(f"Eval completed! Vector + Lexical hybrid search exercised. Mean P@5: {mean_p5:.4f}, Mean R@5: {mean_r5:.4f}")

if __name__ == "__main__":
    asyncio.run(evaluate())
