from fastapi import APIRouter

from app.models.schemas import ContatoOut
from app.services.rag_engine import base

router = APIRouter(prefix="/base", tags=["base-de-conhecimento"])

# Contatos do rodapé da página ("Precisa de ajuda agora?"): vêm da base verificada, não do HTML.
AJUDA_IMEDIATA = ["disque-100", "defensoria-es"]


@router.get("/resumo")
def resumo() -> dict:
    """Números da base de conhecimento, para a página mostrar de onde vêm as respostas."""
    datas = [i["verificado_em"] for i in base.itens if i.get("verificado_em")]
    datas += [c["verificado_em"] for c in base.contatos.values() if c.get("verificado_em")]
    return {
        "fontes": len(base.itens),
        "servicos": sum(1 for i in base.itens if i["origem"] == "servico"),
        "leis": sum(1 for i in base.itens if i["origem"] != "servico"),
        "contatos": len(base.contatos),
        "verificado_em": max(datas) if datas else None,
        "ajuda_imediata": [ContatoOut(**base.contatos[c]).model_dump() for c in AJUDA_IMEDIATA if c in base.contatos],
    }
