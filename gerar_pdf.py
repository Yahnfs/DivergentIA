# -*- coding: utf-8 -*-
from fpdf import FPDF

INTEGRANTES = [
    "Debora Cupertino de Araújo Lacerda",
    "João Henrique Silva Reis",
    "Matheus Willian Coco",
    "Polyana Dias",
    "Yahn de Freitas Santos",
]

BLOCOS = [
    {
        "titulo": "Bloco 1: Contexto e Rotina",
        "intro": "",
        "perguntas": [
            {
                "texto": "Pode me contar um pouco sobre você e sobre a pessoa de quem você cuida (idade, diagnóstico/condição principal)?",
                "motivo": "",
            },
            {
                "texto": "Como é a sua rotina diária equilibrando os cuidados, terapias, escola e trabalho?",
                "motivo": "",
            },
            {
                "texto": "Quem geralmente é o responsável na sua casa por correr atrás de laudos, matrículas e benefícios?",
                "motivo": "",
            },
        ],
    },
    {
        "titulo": "Bloco 2: Mapeamento de Dores (Burocracia e Direitos)",
        "intro": "Aqui você investiga o problema que o seu Agente de IA vai resolver.",
        "perguntas": [
            {
                "texto": "Me conte sobre a última vez que você precisou solicitar um serviço público (como mediador escolar, Passe Livre ou renovação de laudo). Como foi a experiência?",
                "motivo": "",
            },
            {
                "texto": "Qual é a sua maior dificuldade hoje ao lidar com o CRAS, secretarias ou prefeituras da Grande Vitória (Serra, Vitória, etc.)?",
                "motivo": "",
            },
            {
                "texto": "Você já teve algum requerimento negado ou precisou voltar ao posto de atendimento por faltar algum documento? Como foi isso?",
                "motivo": "",
            },
        ],
    },
    {
        "titulo": "Bloco 3: Hábitos Tecnológicos (Para desenhar a Interface/UX)",
        "intro": "Você precisa saber como eles usam o celular para desenhar as funcionalidades corretas.",
        "perguntas": [
            {
                "texto": "Quando você tem uma dúvida sobre algum direito do seu filho(a), onde costuma procurar ajuda primeiro? (Google, grupos de WhatsApp, advogados, CRAS?)",
                "motivo": "",
            },
            {
                "texto": "No seu dia a dia, você prefere se comunicar por áudio, mensagens de texto curtas ou ligações?",
                "motivo": "",
            },
            {
                "texto": "Você costuma ter facilidade para ler documentos, baixar cartilhas em PDF ou preencher formulários pelo celular?",
                "motivo": "",
            },
        ],
    },
    {
        "titulo": "Bloco 4: Validação e Expectativas (A Solução)",
        "intro": "Hora de entender como a tecnologia seria recebida.",
        "perguntas": [
            {
                "texto": "Se você tivesse um assistente virtual no celular para te ajudar com toda essa burocracia, qual seria a funcionalidade dos sonhos para salvar o seu tempo?",
                "motivo": "",
            },
            {
                "texto": "Como você se sentiria conversando com uma Inteligência Artificial para tirar dúvidas e receber uma lista de documentos antes de sair de casa? Teria alguma insegurança?",
                "motivo": "",
            },
            {
                "texto": "Pensando nos espaços públicos aqui da região, como postos de saúde e escolas da Serra ou de Vitória, qual é a principal barreira de atendimento ou de acessibilidade que você encontra na prática?",
                "motivo": "Isso ajuda a alimentar o módulo de \"mapeamento colaborativo\" do seu projeto, entendendo se a dor maior da comunidade é física (falta de rampa/estrutura) ou humana (falta de preparo dos atendentes).",
            },
            {
                "texto": "Atualmente, como você organiza e guarda os laudos médicos, receitas e documentos que precisa apresentar com frequência? Fica tudo no papel, no celular, e como é na hora de achar o que precisa?",
                "motivo": "Mapeia o estado atual do usuário. Se a maioria disser que perde laudos impressos ou tem dificuldade de organizar, isso valida com força total a ideia de um \"scanner\" ou de gerar \"checklists em PDF\" no seu aplicativo.",
            },
            {
                "texto": "Se um assistente de inteligência artificial te desse uma orientação sobre uma lei ou um direito que você desconhecia, você se sentiria segura(o) para usar essa informação direto no balcão de atendimento, ou sentiria necessidade de confirmar com um humano primeiro?",
                "motivo": "Testa diretamente uma das dúvidas da sua Matriz CSD (nível de confiança na IA). Isso ajuda a definir se o seu aplicativo precisará exibir a fonte da informação (ex: \"Segundo a Lei Municipal nº X...\") para passar credibilidade.",
            },
            {
                "texto": "Você costuma trocar informações, dicas sobre filas, médicos e direitos com outras pessoas na mesma situação? Como essa troca acontece hoje em dia?",
                "motivo": "Entende o comportamento de rede. Se elas disserem que se ajudam muito por grupos de WhatsApp, isso indica que o seu Agente de IA poderia ter um botão simples de \"Compartilhar roteiro no WhatsApp\", facilitando a vida delas e ajudando a espalhar a sua ferramenta.",
            },
        ],
    },
]


class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Arial", "I", 8)
        self.set_text_color(140, 140, 140)
        self.cell(0, 8, "DivergentIA - Roteiro de Entrevista", align="L")
        self.cell(0, 8, f"Página {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        pass



pdf = PDF(format="A4")
FONTS_DIR = r"C:\Windows\Fonts"
pdf.add_font("Arial", "", f"{FONTS_DIR}\\arial.ttf")
pdf.add_font("Arial", "B", f"{FONTS_DIR}\\arialbd.ttf")
pdf.add_font("Arial", "I", f"{FONTS_DIR}\\ariali.ttf")
pdf.add_font("Arial", "BI", f"{FONTS_DIR}\\arialbi.ttf")
pdf.set_auto_page_break(auto=True, margin=18)
pdf.set_margins(20, 18, 20)

# ---------- Capa ----------
pdf.add_page()
pdf.ln(30)
pdf.set_font("Arial", "B", 26)
pdf.set_text_color(30, 30, 30)
pdf.cell(0, 14, "Projeto DivergentIA", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Arial", "", 15)
pdf.set_text_color(90, 90, 90)
pdf.cell(0, 10, "Roteiro de Entrevista - Pesquisa com Usuários", align="C", new_x="LMARGIN", new_y="NEXT")
pdf.ln(14)

pdf.set_draw_color(200, 200, 200)
pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
pdf.ln(10)

pdf.set_font("Arial", "B", 13)
pdf.set_text_color(30, 30, 30)
pdf.cell(0, 9, "Integrantes do Grupo", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)
pdf.set_font("Arial", "", 12)
pdf.set_text_color(50, 50, 50)
for nome in INTEGRANTES:
    pdf.cell(6, 8, "-", align="L")
    pdf.cell(0, 8, nome, new_x="LMARGIN", new_y="NEXT")

pdf.ln(10)
pdf.set_draw_color(200, 200, 200)
pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
pdf.ln(8)

pdf.set_font("Arial", "", 11)
pdf.set_text_color(90, 90, 90)
pdf.multi_cell(
    0,
    6,
    "Este documento reúne as 15 perguntas do roteiro de entrevista utilizado para "
    "compreender a rotina, as dificuldades burocráticas e os hábitos tecnológicos de "
    "cuidadores de pessoas com deficiência ou condições especiais, com o objetivo de "
    "validar e orientar o desenvolvimento do Agente de IA do projeto.",
    align="J",
    new_x="LMARGIN",
    new_y="NEXT",
)

pdf.set_y(-30)
pdf.set_font("Arial", "I", 9)
pdf.set_text_color(140, 140, 140)
pdf.cell(0, 6, "Grande Vitória - ES  |  2026", align="C")

# ---------- Perguntas ----------
pdf.add_page()
pdf.set_text_color(0, 0, 0)
pdf.set_font("Arial", "B", 17)
pdf.cell(0, 10, "15 Perguntas sobre o Projeto", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

contador = 1
for bloco in BLOCOS:
    if pdf.get_y() > pdf.h - 45:
        pdf.add_page()

    pdf.set_font("Arial", "B", 13.5)
    pdf.set_text_color(20, 70, 130)
    pdf.multi_cell(0, 8, bloco["titulo"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)

    if bloco["intro"]:
        pdf.set_font("Arial", "I", 10.5)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 6, bloco["intro"], new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    pdf.ln(2)

    for pergunta in bloco["perguntas"]:
        if pdf.get_y() > pdf.h - 35:
            pdf.add_page()

        pdf.set_font("Arial", "B", 11)
        num_w = 9
        y_start = pdf.get_y()
        pdf.cell(num_w, 6.5, f"{contador}.", align="L")
        pdf.set_x(pdf.l_margin + num_w)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(0, 6.5, f'"{pergunta["texto"]}"', align="J", new_x="LMARGIN", new_y="NEXT")

        if pergunta["motivo"]:
            pdf.set_x(pdf.l_margin + num_w)
            pdf.set_font("Arial", "I", 9.5)
            pdf.set_text_color(110, 110, 110)
            pdf.multi_cell(0, 5.5, f'Por que perguntar: {pergunta["motivo"]}', align="J", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

        pdf.ln(3)
        contador += 1

    pdf.ln(3)

out_path = "roteiro_entrevista_divergentia.pdf"
pdf.output(out_path)
print(f"PDF gerado: {out_path}")
