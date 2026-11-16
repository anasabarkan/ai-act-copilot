"""
Évaluation de la recherche : Hit Rate@k et MRR sur le jeu de questions.
Usage : python src/evaluate.py
"""
import json
from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from index import COLLECTION, MODELE, QDRANT_PATH

ROOT = Path(__file__).resolve().parent.parent
EVAL_PATH = ROOT / "data" / "eval" / "questions.jsonl"
K = 5


def est_correct(payload, attendu):
    """Correct si le chunk est l'attendu, ou si son parent est l'attendu."""
    return payload["id"] == attendu or payload.get("parent") == attendu


if __name__ == "__main__":
    with EVAL_PATH.open(encoding="utf-8") as f:
        questions = [json.loads(ligne) for ligne in f if ligne.strip()]

    model = SentenceTransformer(MODELE)
    client = QdrantClient(path=str(QDRANT_PATH))

    hits, somme_rr = 0, 0.0
    for q in questions:
        vecteur = model.encode("query: " + q["question"], normalize_embeddings=True)
        resultats = client.query_points(COLLECTION, query=vecteur.tolist(), limit=K).points

        # Le rang de la première bonne réponse, ou None si elle n'est pas dans le top K
        rang = next((i for i, r in enumerate(resultats, start=1)
                     if est_correct(r.payload, q["attendu"])), None)
        if rang:
            hits += 1
            somme_rr += 1 / rang

        statut = "✅" if rang else "❌"
        print(f"{statut} rang={str(rang or '-'):>2}  {q['attendu']:18s} {q['question'][:60]}")
    client.close()

    n = len(questions)
    print(f"\nHit Rate@{K} = {hits}/{n} = {hits / n:.2f}")
    print(f"MRR          = {somme_rr / n:.2f}")