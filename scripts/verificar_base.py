"""Verifica a base de conhecimento (data/*.json) contra as fontes oficiais.

  1. Links: todo endereço da base precisa responder (sem erro e sem "página não encontrada").
  2. Telefones: cada número de um contato precisa aparecer na página oficial de origem (fonte_url).

Uso:   python scripts/verificar_base.py
Saída: um relatório no terminal; código de saída 1 se algo precisar de revisão humana.

Roda de tempos em tempos (ex.: a cada mês) para manter a base confiável: os órgãos mudam telefones e
páginas sem avisar. Item que falha aqui NÃO deve ser mostrado como verdade ao usuário até ser revisado.
"""
import io
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx

DATA = Path(__file__).resolve().parent.parent / "data"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SOFT_404 = re.compile(r"p[aá]gina n[aã]o encontrada|error404|erro\.php", re.I)


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data):
        if not self._ignorar:
            self.partes.append(data)


_cache: dict[str, tuple[int | None, str, str]] = {}  # url -> (status, texto, aviso)


def baixar(url: str) -> tuple[int | None, str, str]:
    """Baixa a URL uma vez. Devolve (status, texto visível, aviso)."""
    if url in _cache:
        return _cache[url]
    aviso = ""
    resposta = None
    for validar in (True, False):
        try:
            resposta = httpx.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR"},
                                 follow_redirects=True, timeout=40, verify=validar)
            if not validar:
                aviso = "certificado do servidor incompleto (problema do site, não da base)"
            break
        except httpx.ConnectError as erro:
            if validar and "CERTIFICATE" in str(erro).upper():
                continue
            _cache[url] = (None, "", f"falha de conexão: {erro}")
            return _cache[url]
        except httpx.HTTPError as erro:
            _cache[url] = (None, "", f"erro: {erro}")
            return _cache[url]
    if resposta is None:
        _cache[url] = (None, "", "sem resposta")
        return _cache[url]

    tipo = resposta.headers.get("content-type", "")
    if "pdf" in tipo or url.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader  # opcional: só para conferir PDFs

            texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(resposta.content)).pages)
        except ImportError:
            texto, aviso = "", (aviso + " PDF não conferido (instale pypdf)").strip()
    else:
        extrator = _Texto()
        extrator.feed(resposta.text)
        texto = " ".join("".join(extrator.partes).split())
        if SOFT_404.search(str(resposta.url)) or SOFT_404.search(texto[:1500]):
            aviso = (aviso + " página não encontrada (o site responde 200, mas mostra erro 404)").strip()
    _cache[url] = (resposta.status_code, texto, aviso)
    return _cache[url]


def digitos(numero: str) -> str:
    return re.sub(r"\D", "", numero)


def telefone_na_pagina(numero: str, texto: str) -> bool:
    d = digitos(numero)
    if len(d) <= 4:  # números curtos (100, 135, 156, 162, 166): palavra isolada
        return re.search(rf"(?<!\d){d}(?!\d)", texto) is not None
    cauda = d[-8:]  # ignora DDD e o 9 extra: a página pode mostrar de jeitos diferentes
    # Procura os 8 dígitos finais, aceitando espaço, ponto ou hífen entre eles ("3198-3300", "3382 - 5484").
    # (Extrair "sequências de dígitos" falharia com telefones colados, como "98166-0142 98182-0568".)
    padrao = r"[\s.\-]{0,3}".join(cauda)
    return re.search(padrao, texto) is not None


def carregar(nome: str) -> list[dict]:
    return json.loads((DATA / nome).read_text(encoding="utf-8"))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    leis, servicos, contatos = carregar("leis.json"), carregar("servicos.json"), carregar("contatos.json")
    ids_contatos = {c["id"] for c in contatos}
    problemas = 0

    print("== Referências cruzadas ==")
    for s in servicos:
        for cid in s.get("contatos", []):
            if cid not in ids_contatos:
                print(f"  ✘ serviço '{s['id']}' cita contato inexistente '{cid}'")
                problemas += 1
    print("  ok" if not problemas else "")

    urls: dict[str, list[str]] = {}
    for item in [*leis, *servicos, *contatos]:
        for link in item.get("links", []):
            urls.setdefault(link["url"], []).append(item["id"])
        for campo in ("site", "fonte_url"):
            if item.get(campo):
                urls.setdefault(item[campo], []).append(item["id"])

    print(f"\n== Links ({len(urls)} endereços) ==")
    for url, donos in sorted(urls.items()):
        status, _, aviso = baixar(url)
        ok = status is not None and status < 400 and "não encontrada" not in aviso
        marca = "✔" if ok else "✘"
        extra = f"  [{aviso}]" if aviso else ""
        print(f"  {marca} {status or '---'}  {url}{extra}")
        if not ok:
            print(f"        usado em: {', '.join(sorted(set(donos)))}")
            problemas += 1

    print("\n== Telefones (conferidos na página de origem) ==")
    for c in contatos:
        numeros = [t["numero"] for t in c.get("telefones", [])] + [w["numero"] for w in c.get("whatsapp", [])]
        numeros += [t for u in c.get("unidades", []) for t in u.get("telefones", [])]
        if not numeros:
            continue
        status, texto, aviso = baixar(c["fonte_url"])
        if not texto:
            print(f"  ? {c['id']}: não deu para ler a página de origem ({aviso or status}); conferir à mão")
            problemas += 1
            continue
        faltando = [n for n in numeros if not telefone_na_pagina(n, texto)]
        if faltando:
            print(f"  ✘ {c['id']}: não encontrei na página de origem: {', '.join(faltando)}")
            problemas += 1
        else:
            print(f"  ✔ {c['id']}: {len(numeros)} número(s) conferidos")

    print(f"\n{'TUDO CONFERE' if not problemas else str(problemas) + ' item(ns) para revisão humana'}")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
