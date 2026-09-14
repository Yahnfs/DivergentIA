import io
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

from app.models.schemas import Roteiro


def gerar_pdf_roteiro(roteiro: Roteiro) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elementos = []

    elementos.append(Paragraph("Roteiro de Acessibilidade e Inclusão Social", styles["Title"]))
    elementos.append(Paragraph(f"Gerado em {date.today().strftime('%d/%m/%Y')}", styles["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Resumo", styles["Heading2"]))
    elementos.append(Paragraph(roteiro.resumo, styles["Normal"]))
    elementos.append(Spacer(1, 0.5 * cm))

    elementos.append(Paragraph("Passos a seguir", styles["Heading2"]))
    itens_lista = []
    for passo in sorted(roteiro.passos, key=lambda p: p.ordem):
        texto = f"<b>{passo.ordem}. {passo.titulo}</b><br/>{passo.descricao}"
        if passo.documentos:
            texto += f"<br/><i>Documentos necessários:</i> {', '.join(passo.documentos)}"
        if passo.orgao_responsavel:
            texto += f"<br/><i>Órgão responsável:</i> {passo.orgao_responsavel}"
        itens_lista.append(ListItem(Paragraph(texto, styles["Normal"]), spaceAfter=10))
    elementos.append(ListFlowable(itens_lista, bulletType="bullet"))
    elementos.append(Spacer(1, 0.5 * cm))

    if roteiro.aviso:
        elementos.append(Paragraph("Aviso importante", styles["Heading2"]))
        elementos.append(Paragraph(roteiro.aviso, styles["Normal"]))
        elementos.append(Spacer(1, 0.5 * cm))

    if roteiro.fontes_citadas:
        elementos.append(Paragraph("Fontes consultadas", styles["Heading2"]))
        elementos.append(Paragraph(", ".join(roteiro.fontes_citadas), styles["Normal"]))

    doc.build(elementos)
    return buffer.getvalue()
