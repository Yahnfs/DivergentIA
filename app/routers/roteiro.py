from fastapi import APIRouter, Response

from app.models.schemas import PdfRequest
from app.services.pdf_generator import gerar_pdf_roteiro

router = APIRouter(prefix="/roteiro", tags=["roteiro"])


@router.post("/pdf")
def gerar_pdf(dados: PdfRequest) -> Response:
    return Response(
        content=gerar_pdf_roteiro(dados),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=roteiro_acessibilidade.pdf"},
    )
