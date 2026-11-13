# AI Act Copilot

**A retrieval-augmented assistant for the EU AI Act (Regulation (EU) 2024/1689), working on the official French text.**

> 🚧 **Work in progress.** Ingestion, indexing and semantic search are done. Answer generation with citations, evaluation and deployment are next (see [Roadmap](#roadmap)).

The goal is a RAG system that answers questions about the AI Act and **cites the exact article, paragraph or definition** it relies on, and whose quality is **measured**, not assumed.

---

## Pipeline

```
AI Act PDF (French, 144 pages)
        │
        ▼
1. Ingestion        src/ingest.py   ✅
   cleaning + structure-aware chunking + automated tests
        │
        ▼
2. Indexing         src/index.py    ✅
   multilingual embeddings → Qdrant vector database
        │
        ▼
3. Retrieval        src/search.py   ✅ (baseline)
   semantic top-k search
        │
        ▼
4. Generation       🔜  LLM answer with article-level citations
5. Evaluation       🔜  question set + retrieval and RAGAS metrics
6. Serving          🔜  FastAPI + Docker + demo
```

---

## What is implemented

### 1. Structure-aware ingestion (`src/ingest.py`)

Instead of splitting the text every *N* characters, the regulation is split along its **legal structure**, so that every chunk can be cited precisely:

| Chunk type   | Count | Example id            |
|--------------|------:|-----------------------|
| Recital (considérant) | 180 | `considerant-13` |
| Article      | 113   | `article-5`           |
| Annex        | 13    | `annexe-III`          |
| Definition   | 68    | `article-3-point-4`   |
| **Total**    | **374** |                     |

Each chunk carries metadata: type, number, title, chapter, source and, for definitions, its parent article.

**Cleaning challenges solved:**
- Repeated page headers and footers (`FR JO L du 12.7.2024`, `44/144 ELI: …`) removed.
- **Footnotes** use the same `(1)`, `(2)` numbering as recitals. They are detected by their content (`JO C`, `Règlement`, `Directive`, `Position`…) so that exactly 180 recitals remain.
- French legal convention handled: article 1 is written *« Article premier »*.
- Lines broken by the PDF layout are re-joined, while keeping list items (`1.`, `a)`, `i)`) on separate lines.

**Parent-child chunking for definitions.** Article 3 (« Définitions ») is 19,000 characters long and defines 68 terms. Embedded as a single vector, it becomes too vague to retrieve. Each definition is therefore stored as its own child chunk, linked to its parent article.

**Automated tests.** The script fails if it does not recover the official structure: 180 recitals, 113 articles numbered 1 to 113, 13 annexes and 68 definitions.

### 2. Indexing (`src/index.py`)

- Embedding model: [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) (384 dimensions, runs on CPU), with the `passage:` / `query:` prefixes the e5 family expects.
- Vector store: [Qdrant](https://qdrant.tech/) in local mode, cosine distance, with the chunk metadata stored as payload.

### 3. Semantic search (`src/search.py`)

```bash
python src/search.py "Qu'est-ce qu'un déployeur ?"
```

```
1. 0.866  article-3-point-4      Définition : déployeur
2. 0.851  considerant-13         Considérant 13
3. 0.844  article-3-point-7      Définition : distributeur
...
```

---

## Early findings (baseline)

Manual tests on a first set of questions already show where the baseline succeeds and fails:

- ✅ **Parent-child chunking works**: the exact definition of *déployeur* ranks first, while the full 19,000-character article 3 does not appear in the top 5.
- ❌ **"Which AI practices are prohibited?"** — article 5, which lists them, is **not in the top 5**; only recitals are returned. Likely causes:
  - **Truncation**: e5-small reads at most 512 tokens, i.e. roughly the first 16 % of article 5 (12,287 characters).
  - **Style mismatch**: recitals explain in natural language, close to user questions; articles are written as legal lists.
  - **Volume**: recitals outnumber articles and several recitals often cover the same topic.
- ⚠️ **"What are the fines?"** — article 99 « Sanctions » is retrieved, but only in 4th position.
- ⚠️ **Similarity scores are compressed** (an unrelated sentence about couscous scored 0.744 against a top result of 0.851): absolute scores cannot be used as a relevance threshold; only the ranking is meaningful.

These observations drive the next steps, and each improvement will be **measured** on an evaluation set.

---

## Roadmap

- [x] PDF ingestion, cleaning and structure-aware chunking with tests
- [x] Parent-child chunking for the 68 definitions
- [x] Embeddings + Qdrant index + semantic search (baseline)
- [ ] Split long articles into paragraph-level child chunks (fixes truncation)
- [ ] Evaluation set of 30–50 questions with expected articles; measure hit rate @5 and MRR
- [ ] Hybrid search (BM25 + embeddings) and a cross-encoder reranker, measured against the baseline
- [ ] Handle the 2026 *Digital Omnibus on AI* amendments
- [ ] Answer generation with article-level citations
- [ ] Answer quality evaluation (RAGAS / LLM-as-a-judge)
- [ ] FastAPI service, Docker image and a demo interface

---

## Getting started

**1. Install the dependencies** (Python 3.10+):

```bash
pip install -r requirements.txt
```

**2. Download the regulation.** On [EUR-Lex](https://eur-lex.europa.eu/), open Regulation (EU) 2024/1689 in French, download the PDF and save it as:

```
data/raw/ai_act_fr.pdf
```

**3. Run the pipeline:**

```bash
python src/ingest.py      # PDF -> data/processed/chunks.jsonl (with tests)
python src/index.py       # chunks -> local Qdrant index in data/qdrant/
python src/search.py "Quelles pratiques d'IA sont interdites ?"
```

The first run downloads the embedding model (about 470 MB).

---

## Project structure

```
ai-act-copilot/
├── data/
│   ├── raw/            # source PDF (not versioned)
│   ├── processed/      # generated chunks (not versioned)
│   └── qdrant/         # local vector index (not versioned)
├── notebooks/
│   ├── 01_exploration.ipynb
│   └── 02_embeddings.ipynb
├── src/
│   ├── ingest.py
│   ├── index.py
│   └── search.py
├── requirements.txt
└── README.md
```

---

## Author

**Anass Abarkane** — State Engineer in Computer Science, MSc in Artificial Intelligence student at ECE Paris.
Looking for a 6-month end-of-studies internship in Generative AI / LLM engineering from April 2027.

[GitHub](https://github.com/anasabarkan) · [LinkedIn](https://www.linkedin.com/in/anass-abarkane)

## License

MIT