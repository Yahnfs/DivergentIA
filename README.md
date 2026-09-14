# DivergentIA

Agente de IA para triagem e guia de acessibilidade/inclusão social. Ajuda pessoas
com deficiência (PCD), pessoas neurodivergentes (autistas, TDAH) e seus
cuidadores a encontrar direitos legais, serviços públicos e locais acessíveis
na Grande Vitória (ES), gerando um roteiro personalizado em PDF.

## Arquitetura

- **Backend**: FastAPI (Python)
- **LLM**: plugável via `.env` — roda com **Ollama local (gratuito)** por padrão,
  com opção de trocar para **Claude API (Anthropic)** sem alterar código
- **RAG**: recuperação por TF-IDF sobre uma base de conhecimento estruturada
  (`data/leis.json`, `data/servicos.json`)
- **Mapeamento colaborativo**: locais acessíveis cadastrados pela comunidade,
  persistidos em SQLite (`app/db.py`)
- **PDF**: geração do roteiro personalizado com ReportLab

## Como rodar

### 1. Instalar dependências

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

```bash
copy .env.example .env
```

Por padrão, `LLM_PROVIDER=ollama` (100% gratuito, roda local).

### 3. Rodar o modelo local com Ollama

1. Instale o [Ollama](https://ollama.com)
2. Baixe um modelo: `ollama pull llama3.1`
3. Deixe o Ollama rodando (ele já roda como serviço após a instalação, ou use `ollama serve`)

### 4. Subir a API

```bash
uvicorn app.main:app --reload
```

Acesse a documentação interativa em `http://localhost:8000/docs`.

## Trocando para a Claude API (Anthropic)

Quando quiser mais qualidade/confiabilidade nas respostas (recomendado antes de
um piloto real com usuários), edite o `.env`:

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sua_chave_aqui
ANTHROPIC_MODEL=claude-sonnet-5
```

Nenhuma outra mudança de código é necessária — o restante do agente (RAG, PDF,
mapeamento colaborativo) continua igual.

## Endpoints principais

- `POST /chat` — recebe a pergunta do usuário em linguagem natural e retorna
  um roteiro estruturado (passos, documentos, órgãos responsáveis) com base
  na legislação e serviços cadastrados
- `POST /roteiro/pdf` — gera o PDF do roteiro a partir do JSON retornado por `/chat`
- `GET /locais` / `POST /locais` — mapeamento colaborativo de locais acessíveis
  (rampas, banheiro adaptado, Braille, espaços de baixo estímulo sensorial, etc.)

## Base de conhecimento

Os arquivos `data/leis.json` e `data/servicos.json` contêm uma amostra inicial
de leis (federais, estaduais-ES e municipais de Serra/Vitória/Vila Velha) e
serviços públicos (CRAS, CREAS, educação inclusiva, Defensoria Pública, etc.).
**Esses dados são exemplos de estrutura e precisam ser revisados e expandidos
com informações oficiais e atualizadas** antes de qualquer uso real — é aqui
que a parceria com associações de apoio a PCDs/famílias atípicas mencionada no
projeto entra: elas podem validar e enriquecer essa base continuamente.
