import json
import re

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, FonteConsultada, Roteiro
from app.services.llm_provider import LLMProviderError, get_llm_provider
from app.services.rag_engine import rag_engine

router = APIRouter(prefix="/chat", tags=["chat"])

SYSTEM_PROMPT = """\
Você é um agente de triagem e orientação para acessibilidade e inclusão social, \
ajudando pessoas com deficiência (PCD), pessoas neurodivergentes (autistas, TDAH) \
e seus cuidadores/familiares a entenderem seus direitos e os serviços públicos \
disponíveis na Grande Vitória (ES).

REGRAS OBRIGATÓRIAS:
1. Responda APENAS com base no CONTEXTO fornecido abaixo. Nunca invente leis, \
endereços, documentos ou procedimentos que não estejam no contexto.
2. Se o contexto não tiver informação suficiente para responder com segurança, \
diga isso claramente no campo "aviso" e oriente o usuário a buscar confirmação \
no órgão público competente ou na Defensoria Pública.
3. Use linguagem simples, acolhedora e direta, evitando jargão jurídico.
4. Sempre cite o "id" das fontes do contexto que você usou em "fontes_citadas".
5. Responda EXCLUSIVAMENTE em formato JSON válido, seguindo exatamente este esquema, \
sem nenhum texto antes ou depois do JSON:

{
  "resumo": "string com um resumo curto da orientação",
  "passos": [
    {
      "ordem": 1,
      "titulo": "string curta",
      "descricao": "string explicando o passo",
      "documentos": ["lista de documentos necessários, se houver"],
      "orgao_responsavel": "nome do órgão responsável, se houver"
    }
  ],
  "aviso": "string com algum aviso importante, ou null se não houver",
  "fontes_citadas": ["ids das fontes do contexto usadas"]
}
"""


def _montar_contexto(itens: list[dict]) -> str:
    blocos = []
    for item in itens:
        c = item["conteudo"]
        if item["tipo"] == "lei":
            bloco = (
                f"[FONTE id={item['id']} tipo=lei]\n"
                f"Título: {c['titulo']}\n"
                f"Número: {c.get('numero', '')}\n"
                f"Esfera: {c.get('esfera', '')}\n"
                f"Município: {c.get('municipio') or 'aplicável a todos'}\n"
                f"Resumo: {c.get('resumo', '')}"
            )
        else:
            bloco = (
                f"[FONTE id={item['id']} tipo=servico]\n"
                f"Nome: {c['nome']}\n"
                f"Órgão: {c.get('orgao', '')}\n"
                f"Município: {c.get('municipio') or 'aplicável a todos'}\n"
                f"Documentos necessários: {', '.join(c.get('documentos_necessarios', []))}\n"
                f"Fluxo de atendimento: {c.get('fluxo_atendimento', '')}\n"
                f"Contato: {c.get('contato', '')}"
            )
        blocos.append(bloco)
    return "\n\n".join(blocos)


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    texto = re.sub(r"^```(json)?", "", texto).strip()
    texto = re.sub(r"```$", "", texto).strip()
    return json.loads(texto)


@router.post("", response_model=ChatResponse)
def conversar(payload: ChatRequest) -> ChatResponse:
    itens_relevantes = rag_engine.retrieve(payload.mensagem, top_k=5, municipio=payload.municipio)

    if not itens_relevantes:
        return ChatResponse(
            resposta_texto=(
                "Não encontrei informações na minha base de conhecimento sobre essa solicitação. "
                "Recomendo procurar diretamente a Defensoria Pública ou a Secretaria de Assistência "
                "Social do seu município para orientação personalizada."
            ),
            roteiro=None,
            fontes_consultadas=[],
        )

    contexto = _montar_contexto(itens_relevantes)
    user_prompt = f"CONTEXTO:\n{contexto}\n\nPERGUNTA DO USUÁRIO:\n{payload.mensagem}"

    provider = get_llm_provider()
    try:
        resposta_bruta = provider.generate(SYSTEM_PROMPT, user_prompt)
    except LLMProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    fontes_consultadas = [
        FonteConsultada(id=item["id"], tipo=item["tipo"], titulo=item["titulo"], score=1.0)
        for item in itens_relevantes
    ]

    try:
        dados = _extrair_json(resposta_bruta)
        roteiro = Roteiro(**dados)
        return ChatResponse(
            resposta_texto=roteiro.resumo,
            roteiro=roteiro,
            fontes_consultadas=fontes_consultadas,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return ChatResponse(
            resposta_texto=resposta_bruta,
            roteiro=None,
            fontes_consultadas=fontes_consultadas,
        )
