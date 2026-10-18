import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from app.models.schemas import ContatoOut, PdfRequest

INDIGO = colors.HexColor("#312e81")
CINZA = colors.HexColor("#4b5563")
LINK = "#1d4ed8"


def _data(iso: str | None) -> str:
    """'2026-09-21' -> '21/09/2026'."""
    if not iso:
        return ""
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def _link(url: str, texto: str | None = None) -> str:
    # O Paragraph do ReportLab lê marcação XML: todo texto (do usuário, do LLM ou da base) passa por escape().
    href = escape(url, {'"': "&quot;"})
    return f'<a href="{href}" color="{LINK}"><u>{escape(texto or url)}</u></a>'


def _linhas_contato(c: ContatoOut) -> list[str]:
    linhas = []
    for t in c.telefones:
        linhas.append(f"Telefone: <b>{escape(t.numero)}</b>" + (f" ({escape(t.rotulo)})" if t.rotulo else ""))
    for w in c.whatsapp:
        linhas.append(f"WhatsApp: <b>{escape(w.numero)}</b>" + (f" ({escape(w.rotulo)})" if w.rotulo else ""))
    if c.email:
        linhas.append(f"E-mail: {escape(c.email)}")
    if c.endereco:
        linhas.append(f"Endereço: {escape(c.endereco)}")
    if c.horario:
        linhas.append(f"Horário: {escape(c.horario)}")
    if c.site:
        linhas.append("Site: " + _link(c.site))
    if c.unidade_destaque:
        unidade = next((u for u in c.unidades if u.nome == c.unidade_destaque), None)
        if unidade:
            fones = ", ".join(unidade.telefones)
            linhas.append(f"<b>Unidade do seu bairro: {escape(unidade.nome)}</b>"
                          + (f" – {escape(unidade.endereco)}" if unidade.endereco else "")
                          + (f" – {escape(fones)}" if fones else ""))
    elif c.unidades:
        linhas.append("Unidades:")
        for u in c.unidades:
            fones = ", ".join(u.telefones)
            linhas.append(f"&nbsp;&nbsp;• {escape(u.nome)}" + (f" – {escape(u.endereco)}" if u.endereco else "")
                          + (f" – {escape(fones)}" if fones else ""))
    if c.observacao:
        linhas.append(f"<i>{escape(c.observacao)}</i>")
    return linhas


def _rodape(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "DivergentIA – protótipo de projeto de extensão. Orienta, mas não substitui o atendimento "
                                        "jurídico ou social.")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def gerar_pdf_roteiro(dados: PdfRequest) -> bytes:
    roteiro = dados.roteiro
    contatos = {c.id: c for c in dados.contatos}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                            leftMargin=2 * cm, rightMargin=2 * cm, title=roteiro.titulo, author="DivergentIA")
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=base["Title"], textColor=INDIGO, fontSize=20, leading=24, alignment=TA_LEFT)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], textColor=INDIGO, fontSize=13, spaceBefore=14, spaceAfter=6)
    normal = ParagraphStyle("normal", parent=base["Normal"], fontSize=10.5, leading=14.5)
    pequeno = ParagraphStyle("pequeno", parent=normal, fontSize=9, leading=12, textColor=CINZA)
    passo_titulo = ParagraphStyle("passo", parent=normal, fontSize=11.5, leading=15, spaceAfter=2)
    recuo = ParagraphStyle("recuo", parent=normal, leftIndent=18)

    el = [
        Paragraph("Roteiro de acessibilidade e inclusão social", pequeno),
        Paragraph(escape(roteiro.titulo), titulo),
        Paragraph(f"Gerado em {date.today().strftime('%d/%m/%Y')}. Leve este roteiro ao atendimento e confirme os "
                  "dados com o órgão antes de ir.", pequeno),
        Spacer(1, 0.3 * cm),
        HRFlowable(width="100%", color=INDIGO, thickness=1.2),
        Paragraph("Resumo", h2),
        Paragraph(escape(roteiro.resumo), normal),
    ]

    if roteiro.aviso:
        el += [Spacer(1, 0.2 * cm), Paragraph(f"<b>Atenção:</b> {escape(roteiro.aviso)}", normal)]

    el.append(Paragraph("Passo a passo", h2))
    for passo in sorted(roteiro.passos, key=lambda p: p.ordem):
        bloco = [Paragraph(f"[&nbsp;&nbsp;] <b>{passo.ordem}. {escape(passo.titulo)}</b>", passo_titulo),
                 Paragraph(escape(passo.descricao), recuo)]
        if passo.documentos:
            bloco.append(Paragraph("<b>Documentos:</b> " + escape("; ".join(passo.documentos)), recuo))
        for cid in passo.contato_ids:
            c = contatos.get(cid)
            if c:
                fones = ", ".join(t.numero for t in c.telefones + c.whatsapp)
                bloco.append(Paragraph(f"<b>Contato:</b> {escape(c.nome)}" + (f" – {escape(fones)}" if fones else ""), recuo))
        for link in passo.links:
            bloco.append(Paragraph("<b>Saiba mais:</b> " + _link(link.url, link.titulo), recuo))
        if passo.atencao:
            bloco.append(Paragraph(f"<b>Atenção:</b> {escape(passo.atencao)}", recuo))
        bloco.append(Spacer(1, 0.25 * cm))
        el.append(KeepTogether(bloco))

    if roteiro.direitos:
        el.append(Paragraph("Seus direitos (base legal)", h2))
        for d in roteiro.direitos:
            bloco = [Paragraph(f"<b>{escape(d.titulo)}</b>" + (f" – {escape(d.numero)}" if d.numero else ""), passo_titulo)]
            if d.projeto:
                bloco.append(Paragraph("<i>É um projeto de lei: ainda não é lei.</i>", recuo))
            bloco += [Paragraph("• " + escape(t), recuo) for t in d.trechos]
            bloco += [Paragraph(_link(link.url, link.titulo), recuo) for link in d.links]
            bloco.append(Spacer(1, 0.25 * cm))
            el.append(KeepTogether(bloco))

    apoio = [contatos[i] for i in dados.contatos_de_apoio if i in contatos]
    if apoio:
        el.append(Paragraph("Quem pode ajudar agora", h2))
        for c in apoio:
            bloco = [Paragraph(f"<b>{escape(c.nome)}</b>", passo_titulo)]
            bloco += [Paragraph(linha, recuo) for linha in _linhas_contato(c)]
            bloco.append(Spacer(1, 0.25 * cm))
            el.append(KeepTogether(bloco))

    if dados.fontes:
        el.append(Paragraph("Fontes consultadas", h2))
        el.append(Paragraph("Informações conferidas em fontes oficiais nas datas indicadas. Regras e telefones mudam: "
                            "confirme antes de ir.", pequeno))
        for f in sorted(dados.fontes, key=lambda x: not x.citada):
            texto = "• " + (_link(f.links[0].url, f.titulo) if f.links else escape(f.titulo))
            if f.verificado_em:
                texto += f" <font color='#4b5563'>(verificado em {_data(f.verificado_em)})</font>"
            el.append(Paragraph(texto, pequeno))

    doc.build(el, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
