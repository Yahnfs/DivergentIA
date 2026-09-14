import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _texto_busca_lei(lei: dict) -> str:
    partes = [lei["titulo"], lei.get("resumo", ""), lei.get("numero", ""), " ".join(lei.get("tags", []))]
    return " ".join(partes)


def _texto_busca_servico(servico: dict) -> str:
    partes = [
        servico["nome"],
        servico.get("fluxo_atendimento", ""),
        servico.get("orgao", ""),
        " ".join(servico.get("tags", [])),
    ]
    return " ".join(partes)


class RagEngine:
    def __init__(self) -> None:
        self.itens: list[dict] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.matriz = None
        self._carregar()

    def _carregar(self) -> None:
        with open(DATA_DIR / "leis.json", encoding="utf-8") as f:
            leis = json.load(f)
        with open(DATA_DIR / "servicos.json", encoding="utf-8") as f:
            servicos = json.load(f)

        for lei in leis:
            self.itens.append(
                {
                    "id": lei["id"],
                    "tipo": "lei",
                    "titulo": lei["titulo"],
                    "municipio": lei.get("municipio"),
                    "conteudo": lei,
                    "texto_busca": _texto_busca_lei(lei),
                }
            )
        for servico in servicos:
            self.itens.append(
                {
                    "id": servico["id"],
                    "tipo": "servico",
                    "titulo": servico["nome"],
                    "municipio": servico.get("municipio"),
                    "conteudo": servico,
                    "texto_busca": _texto_busca_servico(servico),
                }
            )

        corpus = [item["texto_busca"] for item in self.itens]
        self.vectorizer = TfidfVectorizer(lowercase=True)
        self.matriz = self.vectorizer.fit_transform(corpus)

    def retrieve(self, pergunta: str, top_k: int = 5, municipio: str | None = None) -> list[dict]:
        query_vec = self.vectorizer.transform([pergunta])
        scores = cosine_similarity(query_vec, self.matriz).flatten()

        resultados = []
        for idx, score in enumerate(scores):
            item = self.itens[idx]
            if municipio and item["municipio"] and item["municipio"].lower() != municipio.lower():
                continue
            resultados.append((score, item))

        resultados.sort(key=lambda x: x[0], reverse=True)
        top = [item for score, item in resultados[:top_k] if score > 0]
        return top


rag_engine = RagEngine()
