from fastapi import APIRouter, Response

from app.models.schemas import Roteiro
from app.services.pdf_generator import gerar_pdf_roteiro

router = APIRouter(prefix="/roteiro", tags=["roteiro"])


@router.post("/pdf")
def gerar_pdf(roteiro: Roteiro) -> Response:
    conteudo_pdf = gerar_pdf_roteiro(roteiro)
    return Response(
        content=conteudo_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=roteiro_acessibilidade.pdf"},
    )
