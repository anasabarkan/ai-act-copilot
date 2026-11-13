"""
Ingestion de l'AI Act : PDF -> chunks JSONL.
Un chunk = un considérant, un article ou une annexe, avec ses métadonnées.
"""
import json
import re
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = ROOT / "data" / "raw" / "ai_act_fr.pdf"
OUT_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
SOURCE = "Règlement (UE) 2024/1689"

# --- Lignes à supprimer ---
ENTETE = re.compile(r"^(FR\s+)?JO L du \d")        # "FR JO L du 12.7.2024"
PIED = re.compile(r"^\d+/\d+\s+ELI:")              # "44/144 ELI: http://..."
NOTE = re.compile(
    r"^\(\d+\)\s+(JO [CL] |Règlement|Directive|Décision|Recommandation"
    r"|Résolution|Conseil européen|Position)"
)

# --- Titres de structure ---
CONSIDERANT = re.compile(r"^\((\d+)\)", re.MULTILINE)
ARTICLE = re.compile(r"^Article (premier|\d+)\s*$", re.MULTILINE)
CHAPITRE = re.compile(r"^CHAPITRE ([IVXLC]+)\s*$", re.MULTILINE)
SECTION = re.compile(r"^SECTION \d+\s*$", re.MULTILINE)
ANNEXE = re.compile(r"^ANNEXE ([IVXLC]+)\s*$", re.MULTILINE)
SIGNATURE = re.compile(r"^Fait à Bruxelles", re.MULTILINE)

# Une ligne qui commence par l'un de ces motifs ouvre un nouveau paragraphe
DEBUT_PARAGRAPHE = re.compile(r"^(\d+\.\s|[a-z]\)\s|\d+\)\s|[ivx]+\)\s|—|–|\(\d+\))")


def extraire_texte(pdf_path):
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() for page in reader.pages)


def nettoyer(texte):
    """Supprime les lignes vides, les en-têtes, les pieds de page et les notes."""
    lignes = []
    for ligne in texte.splitlines():
        l = ligne.strip()
        if not l or ENTETE.match(l) or PIED.match(l) or NOTE.match(l):
            continue
        lignes.append(l)
    return "\n".join(lignes)


def recoller(bloc):
    """Recolle les lignes coupées par la mise en page du PDF."""
    paragraphes = []
    for ligne in bloc.split("\n"):
        if not paragraphes or DEBUT_PARAGRAPHE.match(ligne):
            paragraphes.append(ligne)
        else:
            paragraphes[-1] += " " + ligne
    return "\n".join(paragraphes)


def couper_par(texte, motif):
    """Renvoie une liste (titre trouvé, bloc) : chaque bloc va d'un titre au suivant."""
    matches = list(motif.finditer(texte))
    blocs = []
    for i, m in enumerate(matches):
        fin = matches[i + 1].start() if i + 1 < len(matches) else len(texte)
        blocs.append((m, texte[m.start():fin].strip()))
    return blocs


def retirer_titres_suivants(bloc):
    """Coupe le bloc avant un titre de chapitre, de section ou la signature finale."""
    for motif in (CHAPITRE, SECTION, SIGNATURE):
        m = motif.search(bloc)
        if m:
            bloc = bloc[:m.start()]
    return bloc.strip()


def ligne_suivante(texte, m):
    """La ligne juste après un titre (ex. le nom d'un chapitre)."""
    reste = texte[m.end():].strip()
    return reste.split("\n")[0] if reste else ""


def construire_chunks(texte):
    i_corps = texte.find("ONT ADOPTÉ LE PRÉSENT RÈGLEMENT")
    m_annexes = ANNEXE.search(texte, i_corps)

    preambule = texte[:i_corps]
    corps = texte[i_corps:m_annexes.start()]
    annexes = texte[m_annexes.start():]

    chunks = []

    # 1. Considérants
    for m, bloc in couper_par(preambule, CONSIDERANT):
        n = m.group(1)
        chunks.append({
            "id": f"considerant-{n}", "type": "considerant", "numero": n,
            "titre": f"Considérant {n}", "chapitre": "",
            "texte": recoller(bloc), "source": SOURCE,
        })

    # 2. Articles, avec leur chapitre
    chapitres = [
        (m.start(), f"Chapitre {m.group(1)} — {ligne_suivante(corps, m)}")
        for m in CHAPITRE.finditer(corps)
    ]
    for m, bloc in couper_par(corps, ARTICLE):
        n = "1" if m.group(1) == "premier" else m.group(1)
        lignes = retirer_titres_suivants(bloc).split("\n")
        titre = lignes[1] if len(lignes) > 1 else ""
        chapitre = ""
        for position, nom in chapitres:
            if position < m.start():
                chapitre = nom
        chunks.append({
            "id": f"article-{n}", "type": "article", "numero": n,
            "titre": titre, "chapitre": chapitre,
            "texte": f"Article {n} — {titre}\n" + recoller("\n".join(lignes[2:])),
            "source": SOURCE,
        })

    # 3. Annexes
    for m, bloc in couper_par(annexes, ANNEXE):
        n = m.group(1)
        lignes = bloc.split("\n")
        titre = lignes[1] if len(lignes) > 1 else ""
        chunks.append({
            "id": f"annexe-{n}", "type": "annexe", "numero": n,
            "titre": titre, "chapitre": "",
            "texte": f"Annexe {n} — {titre}\n" + recoller("\n".join(lignes[2:])),
            "source": SOURCE,
        })

    return chunks


def verifier(chunks):
    """Tests automatiques : le découpage doit retrouver la structure officielle."""
    nb = Counter(c["type"] for c in chunks)
    assert nb["considerant"] == 180, f"{nb['considerant']} considérants au lieu de 180"
    assert nb["article"] == 113, f"{nb['article']} articles au lieu de 113"
    assert nb["annexe"] == 13, f"{nb['annexe']} annexes au lieu de 13"

    numeros = [int(c["numero"]) for c in chunks if c["type"] == "article"]
    assert numeros == list(range(1, 114)), "Numérotation des articles incorrecte"
    print("✅ Tous les tests passent :", dict(nb))


def afficher_stats(chunks):
    for t in ("considerant", "article", "annexe"):
        longueurs = [len(c["texte"]) for c in chunks if c["type"] == t]
        print(f"{t:12s} : min={min(longueurs):6d}  max={max(longueurs):6d}  "
              f"moyenne={sum(longueurs) // len(longueurs):6d} caractères")

    print("\nLes 3 chunks les plus longs :")
    for c in sorted(chunks, key=lambda c: len(c["texte"]), reverse=True)[:3]:
        print(f"  {c['id']:15s} {len(c['texte']):6d} caractères — {c['titre'][:60]}")


if __name__ == "__main__":
    texte = nettoyer(extraire_texte(PDF_PATH))
    chunks = construire_chunks(texte)

    verifier(chunks)
    afficher_stats(chunks)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\n{len(chunks)} chunks enregistrés dans {OUT_PATH}")