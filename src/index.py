"""
Indexation : chunks JSONL -> embeddings -> base vectorielle Qdrant (locale).
"""
import json
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
QDRANT_PATH = ROOT / "data" / "qdrant"
COLLECTION = "ai_act"
MODELE = "intfloat/multilingual-e5-small"


def charger_chunks(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f]


if __name__ == "__main__":
    chunks = charger_chunks(CHUNKS_PATH)
    print(f"{len(chunks)} chunks chargés")

    # 1. Embeddings : un vecteur par chunk
    model = SentenceTransformer(MODELE)
    textes = ["passage: " + c["texte"] for c in chunks]
    vecteurs = model.encode(textes, batch_size=16, normalize_embeddings=True,
                            show_progress_bar=True)
    print("Forme de la matrice :", vecteurs.shape)

    # 2. Base vectorielle : on repart de zéro à chaque indexation
    client = QdrantClient(path=str(QDRANT_PATH))
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=vecteurs.shape[1], distance=Distance.COSINE),
    )

    # 3. Chaque point = un vecteur + les métadonnées du chunk
    client.upsert(
        collection_name=COLLECTION,
        points=[
            PointStruct(id=i, vector=v.tolist(), payload=c)
            for i, (v, c) in enumerate(zip(vecteurs, chunks))
        ],
    )
    print(f"✅ {client.count(COLLECTION).count} vecteurs indexés dans Qdrant")
    client.close()