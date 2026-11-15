"""Importa a pesquisa de campo feita pelo grupo em locais_acessiveis_vitoria/ (duas fontes distintas):

  1. locais_acessiveis_vitoria.json (30 lugares com recursos de acessibilidade variados: praia com
     cadeira anfíbia, parque com estímulo sensorial, teatro com Libras etc.) -> vira linhas na tabela
     "locais_acessiveis" (a funcionalidade "Locais acessíveis" do site), já verificadas.

  2. locais_vitoria.json (56 unidades de atendimento — CRAS e UBS — e outros órgãos de apoio/direitos/
     mobilidade) -> alimenta as DUAS coisas: entra em data/contatos.json (mesma estrutura, usada pelo
     chat) E também vira linha em "locais_acessiveis" (2 itens — a praia e o cinema — já chegam pelo
     arquivo 1, então não duplicamos esses dois).

Uso:   python scripts/importar_dados_vitoria.py
Roda uma vez só. É seguro rodar de novo: pula o que já existir (checa por id/nome).
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.db import LocalAcessivelDB, SessionLocal, init_db  # noqa: E402

PASTA_PESQUISA = RAIZ / "locais_acessiveis_vitoria"
CONTATOS_JSON = RAIZ / "data" / "contatos.json"

ENDERECO_SHOPPING_VITORIA = "Av. Américo Buaiz, 200, Shopping Vitória, Enseada do Suá, Vitória - ES"
REPORTADO_POR = "Pesquisa de campo — grupo DivergentIA"

# id (em locais_acessiveis_vitoria.json) -> ajustes manuais (tipo, recursos e, quando faltava,
# endereço/telefone) decididos depois de ler as 30 fichas uma a uma. Comentado por quê.
AJUSTES = {
    "praia_acessivel_curva_da_jurema_vitoria": {
        "tipo": "lazer",
        # rampa/banheiro/vaga: só locais_vitoria.json tinha esses detalhes para esta mesma praia.
        "recursos_acessibilidade": ["cadeira_anfibia", "rampa", "banheiro_adaptado", "vaga_exclusiva"],
    },
    "praia_acessivel_camburi_vitoria": {
        "tipo": "lazer", "recursos_acessibilidade": ["cadeira_anfibia"],
        "endereco": "Praia de Camburi, Jardim Camburi, Vitória - ES",
    },
    "tancredao_paradesporto_vitoria": {"tipo": "lazer", "recursos_acessibilidade": []},
    "parque_pedra_da_cebola_vitoria": {"tipo": "lazer", "recursos_acessibilidade": ["brinquedos_adaptados", "rampa"]},
    "parque_pedra_da_cebola_estimulo_sensorial": {"tipo": "lazer", "recursos_acessibilidade": ["estrutura_sensorial"]},
    "shopping_vitoria_sala_sensorial": {
        "tipo": "comercio", "recursos_acessibilidade": ["baixo_estimulo_sensorial"], "endereco": ENDERECO_SHOPPING_VITORIA,
    },
    "shopping_vitoria_abafadores_ruido": {
        "tipo": "comercio", "recursos_acessibilidade": ["baixo_estimulo_sensorial"], "endereco": ENDERECO_SHOPPING_VITORIA,
    },
    "shopping_vitoria_vagas_tea": {
        "tipo": "comercio", "recursos_acessibilidade": ["vaga_exclusiva"], "endereco": ENDERECO_SHOPPING_VITORIA,
    },
    "cinemark_vitoria_sessao_azul": {
        "tipo": "lazer",
        # banheiro/rampa: detalhe que só locais_vitoria.json tinha para esta mesma sessão.
        "recursos_acessibilidade": ["baixo_estimulo_sensorial", "rampa", "banheiro_adaptado"],
        "endereco": ENDERECO_SHOPPING_VITORIA, "telefones": ["(27) 3335-1000"],
    },
    "seme_vitoria_aee_salas_recursos": {
        "tipo": "educacao", "recursos_acessibilidade": [], "endereco": "Rede municipal de ensino, Vitória - ES",
    },
    "vale_jardim_sensorial": {"tipo": "lazer", "recursos_acessibilidade": ["estrutura_sensorial"]},
    "vale_orquidario": {"tipo": "lazer", "recursos_acessibilidade": ["baixo_estimulo_sensorial"]},
    "vale_vagao_conhecimento": {"tipo": "lazer", "recursos_acessibilidade": []},
    "vale_trilhas_interpretativas": {"tipo": "lazer", "recursos_acessibilidade": []},
    "vale_passeio_onibus_unidade_tubarao": {"tipo": "lazer", "recursos_acessibilidade": []},
    "vale_area_piquenique": {"tipo": "lazer", "recursos_acessibilidade": []},
    "tamar_vitoria_museu_tartarugas": {"tipo": "lazer", "recursos_acessibilidade": ["rampa"]},
    "sesc_gloria_biblioteca_acessivel": {"tipo": "lazer", "recursos_acessibilidade": ["braille", "tecnologia_assistiva"]},
    "sesc_gloria_teatro_libras": {"tipo": "lazer", "recursos_acessibilidade": ["libras"]},
    "theatro_carlos_gomes_acessibilidade": {"tipo": "lazer", "recursos_acessibilidade": ["rampa"]},
    "theatro_carlos_gomes_visita_guiada": {"tipo": "lazer", "recursos_acessibilidade": ["rampa"]},
    "praca_inclusiva_viver_vitoria_praca_dos_desejos": {
        "tipo": "lazer", "recursos_acessibilidade": ["brinquedos_adaptados", "estrutura_sensorial"],
    },
    "praca_inclusiva_viver_vitoria_parque_moscoso": {"tipo": "lazer", "recursos_acessibilidade": ["brinquedos_adaptados"]},
    "amaes_goiabeiras_vitoria": {
        "tipo": "apoio_especializado", "recursos_acessibilidade": [],
        "observacoes_extra": " · amaes@amaes.org.br",
    },
    "cap_es_deficiencia_visual_praia_do_sua": {"tipo": "apoio_especializado", "recursos_acessibilidade": ["braille"]},
    "ilbes_instituto_luiz_braille_es": {
        "tipo": "apoio_especializado", "recursos_acessibilidade": ["braille", "tecnologia_assistiva"],
        "endereco": "Vitória - ES",
    },
    "seme_vitoria_lego_braille": {
        "tipo": "educacao", "recursos_acessibilidade": ["braille"], "endereco": "Rede municipal de ensino, Vitória - ES",
    },
    "palacio_anchieta_sinalizacao_acessivel": {"tipo": "lazer", "recursos_acessibilidade": ["rampa"]},
    "bpes_levy_curcio_sinalizacao_acessivel": {"tipo": "lazer", "recursos_acessibilidade": ["rampa"]},
    "bpes_levy_curcio_acervo_audio_ebooks": {"tipo": "lazer", "recursos_acessibilidade": ["tecnologia_assistiva"]},
}


def _endereco(item: dict) -> str:
    if item.get("endereco"):
        return item["endereco"]
    if item.get("bairro"):
        return f"{item['bairro']}, {item['municipio']} - ES"
    return f"{item['municipio']} - ES"


def importar_locais_acessiveis(db) -> int:
    with open(PASTA_PESQUISA / "locais_acessiveis_vitoria.json", encoding="utf-8") as f:
        itens = json.load(f)

    novos = 0
    for item in itens:
        ajuste = AJUSTES[item["id"]]
        nome = item["unidade"]
        if db.query(LocalAcessivelDB).filter(LocalAcessivelDB.nome == nome).first():
            continue  # já importado numa rodada anterior

        observacoes = item["orgao"] + ajuste.get("observacoes_extra", "")
        db.add(LocalAcessivelDB(
            nome=nome, municipio=item["municipio"], bairro=item.get("bairro"),
            endereco=ajuste.get("endereco") or _endereco(item), tipo=ajuste["tipo"],
            recursos_acessibilidade=ajuste["recursos_acessibilidade"],
            telefones=ajuste.get("telefones") or item.get("telefones") or [],
            horario_funcionamento=item.get("horario_funcionamento"),
            observacoes=observacoes, reportado_por=REPORTADO_POR, verificado=True,
            fonte_url=item.get("fonte_url"), verificado_em=item.get("verificado_em"),
        ))
        novos += 1
    db.commit()
    return novos


# locais_vitoria.json descreve acessibilidade em frases fixas (campos "acessibilidade_fisica" e
# "acessibilidade_sensorial"), ao contrário das etiquetas livres do outro arquivo — por isso aqui dá
# pra mapear por palavra-chave com segurança, em vez de decidir item a item.
PALAVRA_PARA_RECURSO = [
    ("rampa", "rampa"), ("elevador", "rampa"), ("plataforma", "rampa"),
    ("banheiro", "banheiro_adaptado"), ("sanitári", "banheiro_adaptado"),
    ("atendimento priorit", "atendimento_preferencial"), ("guichês", "atendimento_preferencial"),
    ("piso tátil", "piso_tatil"), ("podotátil", "piso_tatil"), ("sinalização tátil", "piso_tatil"),
    ("vaga", "vaga_exclusiva"),
    ("libras", "libras"),
    ("braille", "braille"),
    ("baixo estímulo", "baixo_estimulo_sensorial"), ("controle de ruído", "baixo_estimulo_sensorial"),
    ("comunicação aumentativa", "tecnologia_assistiva"), ("comunicação alternativa", "tecnologia_assistiva"),
    ("alto contraste", "alto_contraste"), ("visual contrastante", "alto_contraste"),
]

CATEGORIA_PARA_TIPO = {
    "Saúde Básica e Urgência": "saude",
    "Assistência Social e Cidadania": "orgao_publico",
    "Reabilitação e Apoio Especializado": "apoio_especializado",
    "Garantia de Direitos": "orgao_publico",
    "Mobilidade e Isenções": "orgao_publico",
}

# já chegam pelo locais_acessiveis_vitoria.json (mesmo lugar, verificado em datas diferentes) — não duplicar.
IDS_SERVICOS_JA_SAO_LOCAIS = {"praia_acessivel_curva_jurema_vitoria", "cinema_cinemark_sessao_azul_vitoria"}


def _recursos_do_texto(item: dict) -> list[str]:
    texto = " ".join(item.get("acessibilidade_fisica", []) + item.get("acessibilidade_sensorial", [])).lower()
    vistos: list[str] = []
    for palavra, recurso in PALAVRA_PARA_RECURSO:
        if palavra in texto and recurso not in vistos:
            vistos.append(recurso)
    return vistos


def importar_locais_de_servicos(db) -> int:
    """As mesmas 56 unidades de locais_vitoria.json, agora também como cards em "Locais acessíveis"."""
    with open(PASTA_PESQUISA / "locais_vitoria.json", encoding="utf-8") as f:
        itens = json.load(f)

    novos = 0
    for item in itens:
        if item["id"] in IDS_SERVICOS_JA_SAO_LOCAIS or item["categoria"] not in CATEGORIA_PARA_TIPO:
            continue
        nome = item["nome"]
        if db.query(LocalAcessivelDB).filter(LocalAcessivelDB.nome == nome).first():
            continue

        db.add(LocalAcessivelDB(
            nome=nome, municipio=item["municipio"], bairro=item.get("bairro"), endereco=item["endereco"],
            tipo=CATEGORIA_PARA_TIPO[item["categoria"]], recursos_acessibilidade=_recursos_do_texto(item),
            telefones=item.get("telefones", []), horario_funcionamento=item.get("horario_funcionamento"),
            observacoes=". ".join(item.get("servicos_oferecidos", [])) + ".",
            reportado_por=REPORTADO_POR, verificado=True,
            fonte_url=item.get("fonte_url"), verificado_em=item.get("verificado_em"),
        ))
        novos += 1
    db.commit()
    return novos


def _unidade(item: dict) -> dict:
    return {"nome": item["nome"], "endereco": item["endereco"], "telefones": item["telefones"], "bairros": item["bairro"]}


def _contato_simples(item: dict) -> dict:
    texto = ". ".join(item.get("servicos_oferecidos", [])) + "."
    acess = item.get("acessibilidade_fisica", []) + item.get("acessibilidade_sensorial", [])
    if acess:
        texto += " Acessibilidade: " + "; ".join(acess) + "."
    return {
        "id": item["id"], "nome": item["nome"], "municipio": item["municipio"],
        "telefones": [{"numero": t} for t in item.get("telefones", [])],
        "whatsapp": [], "email": None, "site": item.get("fonte_url"), "endereco": item.get("endereco"),
        "horario": item.get("horario_funcionamento"), "observacao": texto,
        "fonte_url": item.get("fonte_url"), "verificado_em": item.get("verificado_em"), "unidades": [],
    }


# ids de locais_vitoria.json que já existem (com outro endereço!) em data/contatos.json — ver aviso no
# relatório final do script. Não importamos de novo por cima; é humano que precisa decidir qual valer.
IDS_COM_CONFLITO = {"sefaz_es_agencia_receita_vitoria", "casa_do_cidadao_itarare_vitoria"}


def importar_contatos(contatos: list[dict]) -> tuple[list[dict], int, list[str]]:
    with open(PASTA_PESQUISA / "locais_vitoria.json", encoding="utf-8") as f:
        itens = json.load(f)

    by_id = {c["id"]: c for c in contatos}
    avisos: list[str] = []
    novos = 0

    cras = itens_por_categoria = None
    cras_existente = by_id.get("cras-vitoria")
    if cras_existente:
        nomes_ja_presentes = {u["nome"] for u in cras_existente["unidades"]}
        for item in itens:
            if item["categoria"] == "Assistência Social e Cidadania" and item["nome"] not in nomes_ja_presentes:
                cras_existente["unidades"].append(_unidade(item))
                novos += 1

    ubs_itens = [i for i in itens if i["categoria"] == "Saúde Básica e Urgência"]
    if ubs_itens and "ubs-vitoria" not in by_id:
        contatos.append({
            "id": "ubs-vitoria", "nome": f"Unidades de Saúde (UBS) de Vitória ({len(ubs_itens)} unidades)",
            "municipio": "Vitória", "telefones": [], "whatsapp": [], "email": None,
            "site": "https://www.vitoria.es.gov.br/municipe/saude",
            "endereco": None, "horario": "Segunda a sexta-feira, das 7h às 19h (varia por unidade)",
            "observacao": (
                "Todas as unidades têm rampa, banheiro adaptado e atendimento prioritário (Lei "
                "Federal nº 10.048/2000), inclusive para autistas com laudo ou CIPTEA."
            ),
            "fonte_url": "https://www.vitoria.es.gov.br/municipe/saude",
            "verificado_em": max(i["verificado_em"] for i in ubs_itens),
            "unidades": [_unidade(i) for i in ubs_itens],
        })
        novos += 1

    outras_categorias = {"Reabilitação e Apoio Especializado", "Garantia de Direitos", "Mobilidade e Isenções"}
    for item in itens:
        if item["categoria"] not in outras_categorias:
            continue
        if item["id"] in IDS_COM_CONFLITO:
            existente = by_id.get("sefaz-es") if "sefaz" in item["id"] else by_id.get("vitoria-setran-cartao")
            avisos.append(
                f"NÃO importei \"{item['nome']}\" (endereço da pesquisa: {item['endereco']}) porque já existe "
                f"\"{existente['nome']}\" em data/contatos.json com outro endereço ({existente['endereco']}). "
                "Confira qual está certo e ajuste manualmente."
            )
            continue
        if item["id"] in by_id:
            continue
        contatos.append(_contato_simples(item))
        novos += 1

    return contatos, novos, avisos


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        novos_locais = importar_locais_acessiveis(db) + importar_locais_de_servicos(db)
    finally:
        db.close()

    with open(CONTATOS_JSON, encoding="utf-8") as f:
        contatos = json.load(f)
    contatos, novos_contatos, avisos = importar_contatos(contatos)
    with open(CONTATOS_JSON, "w", encoding="utf-8") as f:
        json.dump(contatos, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Locais acessíveis novos: {novos_locais}")
    print(f"Contatos novos/atualizados em data/contatos.json: {novos_contatos}")
    for aviso in avisos:
        print("AVISO:", aviso)


if __name__ == "__main__":
    main()
