import json
import re
import unicodedata
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Municípios da Região Metropolitana da Grande Vitória. Só os três primeiros têm dados municipais na base.
MUNICIPIOS_COBERTOS = ["Vitória", "Serra", "Vila Velha"]
MUNICIPIOS_GV = ["Vitória", "Serra", "Vila Velha", "Cariacica", "Viana", "Guarapari", "Fundão"]

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "pra", "com", "sem", "e", "ou", "que", "se", "ao", "aos", "como", "qual", "quais", "quando",
    "onde", "meu", "minha", "meus", "minhas", "seu", "sua", "ter", "tem", "tenho", "faco", "fazer", "preciso",
    "quero", "gostaria", "saber", "ser", "e", "sao", "esta", "estao", "ha", "mais", "muito", "ja", "so",
    "isso", "esse", "essa", "este", "esta", "eu", "voce", "me", "mim", "lhe", "nao", "sim", "pode", "posso",
}


def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: 'Vitória' e 'vitoria' passam a ser a mesma palavra."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).lower()


def _radical(palavra: str) -> str:
    """Stemming bem simples do português: tira o plural ('escolas' -> 'escola', 'documentos' -> 'documento')."""
    if len(palavra) > 4 and palavra.endswith("oes"):
        return palavra[:-3] + "ao"
    if len(palavra) > 4 and palavra.endswith("res"):
        return palavra[:-2]
    if len(palavra) > 3 and palavra.endswith("s") and not palavra.endswith("ss"):
        return palavra[:-1]
    return palavra


radical = _radical  # exposto para outros módulos


def analisar(texto: str) -> list[str]:
    tokens = [_radical(t) for t in re.findall(r"[a-z0-9]+", normalizar(texto))]
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    bigramas = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    return tokens + bigramas


MUNICIPIO_OUTRO = "Outro município"


def detectar_municipio(texto: str) -> str | None:
    """Acha o município no texto (ex.: 'moro em Vila Velha'). 'outro município' = fora da cobertura."""
    limpo = f" {normalizar(texto)} "
    for nome in MUNICIPIOS_GV:
        if re.search(rf"(?<![a-z]){re.escape(normalizar(nome))}(?![a-z])", limpo):
            return nome
    if re.search(r"outro municipio|outra cidade|outro lugar", limpo):
        return MUNICIPIO_OUTRO
    return None


def detectar_rede(texto: str) -> str | None:
    """Rede de ensino citada no texto: 'estadual' ou 'municipal'."""
    limpo = normalizar(texto)
    if "estadual" in limpo or "sedu" in limpo:
        return "estadual"
    if re.search(r"municipal|prefeitura|\bemef\b|\bcmei\b|\bumei\b|\bseme\b|\bsemed\b", limpo):
        return "municipal"
    return None


def _passos_texto(item: dict) -> list[str]:
    return [f"{p['titulo']} {p['texto']}" for p in item.get("passos", [])]


def _texto_busca(item: dict) -> str:
    """Texto usado na busca. Título e etiquetas contam em dobro, porque dizem do que o item trata."""
    partes = [item["titulo"], item["titulo"], " ".join(item.get("tags", [])), " ".join(item.get("tags", [])),
              item.get("resumo", ""), item.get("quem_pode", ""), item.get("numero", "")]
    partes += _passos_texto(item) + item.get("documentos", []) + item.get("trechos", [])
    return " ".join(p for p in partes if p)


class BaseConhecimento:
    def __init__(self) -> None:
        self.itens: list[dict] = []
        self.contatos: dict[str, dict] = {}
        self._carregar()

    def _carregar(self) -> None:
        def ler(nome: str) -> list[dict]:
            return json.loads((DATA_DIR / nome).read_text(encoding="utf-8"))

        for c in ler("contatos.json"):
            self.contatos[c["id"]] = c
        self.lacunas: list[dict] = ler("lacunas.json")
        for lei in ler("leis.json"):
            self.itens.append({**lei, "origem": "projeto" if lei.get("tipo") == "projeto" else "lei"})
        for servico in ler("servicos.json"):
            self.itens.append({**servico, "origem": "servico"})

        self.por_id = {i["id"]: i for i in self.itens}
        self._indice = {i["id"]: n for n, i in enumerate(self.itens)}
        self.vectorizer = TfidfVectorizer(analyzer=analisar)
        self.matriz = self.vectorizer.fit_transform([_texto_busca(i) for i in self.itens])

        # Para o filtro de relevância: palavras de cada item e as suas etiquetas (tags) já normalizadas.
        self._palavras = [{t for t in analisar(_texto_busca(i)) if "_" not in t} for i in self.itens]
        locais = {tuple(t for t in analisar(m) if "_" not in t) for m in MUNICIPIOS_GV}
        # Nome de cidade não é assunto: 'vitoria' não pode contar como etiqueta exata.
        self._etiquetas = [
            [e for e in (tuple(t for t in analisar(tag) if "_" not in t) for tag in i.get("tags", []))
             if e and e not in locais]
            for i in self.itens
        ]
        # Etiqueta rara diz mais do que etiqueta comum: 'negar' (só na Defensoria) pesa mais que 'escola' (em vários).
        contagem: dict[tuple, int] = {}
        for etiquetas in self._etiquetas:
            for e in set(etiquetas):
                contagem[e] = contagem.get(e, 0) + 1
        self._peso_etiqueta = {e: 1 / n for e, n in contagem.items()}
        # Palavras do título (sem nomes de cidade): quem tem "BPC" no título deve ganhar de quem só o menciona.
        palavras_de_cidade = {t for m in locais for t in m}
        self._tokens_titulo = [
            {t for t in analisar(f"{i['titulo']} {i.get('titulo_curto', '')}") if "_" not in t} - palavras_de_cidade
            for i in self.itens
        ]
        contagem_titulo: dict[str, int] = {}
        for tokens in self._tokens_titulo:
            for t in tokens:
                contagem_titulo[t] = contagem_titulo.get(t, 0) + 1
        self._peso_titulo = {t: 1 / n for t, n in contagem_titulo.items()}

    # -- consulta ---------------------------------------------------------------------------------

    def buscar(self, consulta: str, top_k: int = 4, municipio: str | None = None,
               score_minimo: float = 0.06, mensagem_atual: str | None = None) -> list[dict]:
        """Devolve os itens mais parecidos com a consulta, cada um com o campo 'score'.

        Um item só entra se tiver pelo menos 2 palavras em comum com a consulta ou uma etiqueta exata
        (ex.: "bpc", "passe livre"). Isso evita que uma palavra solta, como "receita" em "receita de bolo",
        traga um serviço sem relação com a pergunta.

        'consulta' pode incluir mensagens anteriores (contexto); as etiquetas exatas só valem para a
        'mensagem_atual', para a pergunta de agora (ex.: "e se a escola negar?") não ser engolida pelo assunto anterior.
        """
        palavras_consulta = {t for t in analisar(consulta) if "_" not in t}
        palavras_atual = {t for t in analisar(mensagem_atual or consulta) if "_" not in t}
        similares = cosine_similarity(self.vectorizer.transform([consulta]), self.matriz).flatten()
        candidatos = []
        for idx, score in enumerate(similares):
            item = self.itens[idx]
            do_municipio = item.get("municipio")
            if municipio and do_municipio and do_municipio != municipio:
                continue  # é de outro município
            achadas = [e for e in self._etiquetas[idx] if set(e) <= palavras_consulta]
            if len(palavras_consulta & self._palavras[idx]) < 2 and not achadas:
                continue
            bonus = 0.5 * sum(self._peso_etiqueta[e] for e in self._etiquetas[idx] if set(e) <= palavras_atual)
            bonus_titulo = 0.3 * sum(self._peso_titulo[t] for t in palavras_atual & self._tokens_titulo[idx])
            score = float(score) + min(0.6, bonus) + min(0.3, bonus_titulo)
            if municipio and do_municipio == municipio:
                score *= 1.3  # o que é do município do usuário vem primeiro
            candidatos.append((score, item))
        candidatos.sort(key=lambda x: x[0], reverse=True)
        return [{**item, "score": round(score, 3)} for score, item in candidatos[:top_k] if score >= score_minimo]

    def etiquetas_batem(self, item_id: str, texto: str) -> int:
        """Quantas etiquetas exatas do item (ex.: 'passe livre', 'bpc') aparecem no texto."""
        palavras = {t for t in analisar(texto) if "_" not in t}
        return sum(1 for e in self._etiquetas[self._indice[item_id]] if set(e) <= palavras)

    def tem_contato_municipal(self, item: dict) -> bool:
        """O item indica contatos que dependem do município do usuário (ex.: os CRAS)?"""
        return any(self.contatos.get(c, {}).get("municipio") for c in item.get("contatos", []))

    def unidade_do_bairro(self, contato_id: str, texto: str) -> str | None:
        """Se o texto cita um bairro atendido por uma unidade (ex.: um CRAS), devolve o nome da unidade."""
        contato = self.contatos.get(contato_id)
        if not contato:
            return None
        limpo = f" {normalizar(texto)} "
        for unidade in contato.get("unidades", []):
            for bairro in re.split(r",|\se\s", unidade.get("bairros") or ""):
                bairro = normalizar(bairro).strip()
                if len(bairro) > 3 and re.search(rf"(?<![a-z]){re.escape(bairro)}(?![a-z])", limpo):
                    return unidade["nome"]
        return None

    def contatos_do_item(self, item: dict, municipio: str | None) -> list[str]:
        """Ids dos contatos de um item que valem para o usuário.

        Contato de um município só aparece se o usuário mora nele. Enquanto o município é desconhecido
        (ou não é coberto), aparecem só os contatos nacionais e estaduais: nunca os de uma cidade "chutada".
        """
        ids = []
        for cid in item.get("contatos", []):
            contato = self.contatos.get(cid)
            if not contato or contato.get("municipio") not in (None, municipio):
                continue
            ids.append(cid)
        return ids

    def detectar_lacuna(self, texto: str) -> dict | None:
        """Pergunta que a base sabidamente NÃO responde (ex.: 'quais escolas têm rampa?'): devolve a lacuna.

        Cada lacuna tem grupos de termos; o texto precisa conter pelo menos um termo de cada grupo.
        """
        limpo = f" {normalizar(texto)} "
        for lacuna in self.lacunas:
            if all(any(termo in limpo for termo in grupo) for grupo in lacuna["gatilhos"]):
                return lacuna
        return None

    def contatos_gerais(self, municipio: str | None) -> list[str]:
        """Canais para quando a base não cobre o assunto: o geral do município e a Defensoria."""
        por_municipio = {
            "Vitória": ["pref-vitoria-156", "pref-vitoria-geral"],
            "Serra": ["serra-ouvidoria"],
            "Vila Velha": ["pref-vv-geral"],
        }
        return [*por_municipio.get(municipio, []), "defensoria-es"]


base = BaseConhecimento()
