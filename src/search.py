"""
Recherche sémantique : une question -> les k chunks les plus proches.
Usage : python src/search.py Quelles pratiques d'IA sont interdites ?
"""
import sys

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from index import COLLECTION, MODELE, QDRANT_PATH

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Qu'est-ce qu'un déployeur ?"
    print("Question :", question, "\n")

    model = SentenceTransformer(MODELE)
    client = QdrantClient(path=str(QDRANT_PATH))

    q = model.encode("query: " + question, normalize_embeddings=True)
    resultats = client.query_points(COLLECTION, query=q.tolist(), limit=5).points

    for rang, r in enumerate(resultats, start=1):
        print(f"{rang}. {r.score:.3f}  {r.payload['id']:22s} {r.payload['titre'][:60]}")
    client.close()