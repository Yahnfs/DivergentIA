# DivergentIA

Agente de IA para triagem e guia de acessibilidade/inclusão social. Ajuda pessoas
com deficiência (PCD), pessoas neurodivergentes (autistas, TDAH) e seus
cuidadores a entender direitos legais, serviços públicos e locais acessíveis
na Grande Vitória (ES) por meio de um chat, gerando um roteiro (checklist)
personalizado — com links oficiais, contatos e documentos — que pode ser
baixado em PDF.

## Princípio de design: o modelo de IA não afirma fatos

Para evitar que o assistente invente leis, telefones ou passos, o trabalho é
dividido assim:

- O **servidor** escolhe as fontes (busca por TF-IDF + etiquetas exatas),
  monta o roteiro com os passos **oficiais, palavra por palavra**, de uma base
  verificada manualmente, anexa os links e contatos dessa mesma base e decide
  deterministicamente o que perguntar (município, rede de ensino, se já existe
  laudo).
- O **modelo de IA local** escreve só uma frase curta reconhecendo o pedido da
  pessoa ("Entendi: você quer..."). Essa frase passa por validação (não pode
  conter números, links, leis ou palavras que a pessoa não usou) antes de ser
  exibida; se falhar ou o modelo estiver fora do ar, o chat continua
  funcionando normalmente, só sem a frase de abertura.
- Quando a base **não tem** a informação (ex.: "quais escolas têm rampa?"),
  o assistente diz isso explicitamente e devolve o contato (com telefone) do
  órgão que pode responder, em vez de arriscar um palpite.

## Arquitetura

- **Frontend**: página web acessível (HTML/CSS/JS puro, sem build) em
  `frontend/`, servida pelo próprio FastAPI: chat + painel de roteiro lado a
  lado (no celular, alternável), teclado, leitor de tela, ajuste de tamanho de
  texto, alto contraste, mais espaçamento e "modo calmo" (sem animações)
- **Backend**: FastAPI (Python), tudo em `app/routers/chat.py` +
  `app/services/rag_engine.py`
- **LLM**: plugável via `.env` — roda com **Ollama local (gratuito)** por
  padrão (`llama3.2:3b`, cabe 100% numa GPU de 6 GB e responde em ~3s, porque
  só escreve uma frase curta), com opção de trocar para **Claude API
  (Anthropic)** sem alterar código
- **RAG**: recuperação por TF-IDF + bônus por etiqueta exata (rarity-weighted)
  sobre uma base de conhecimento verificada (`data/leis.json`,
  `data/servicos.json`, `data/contatos.json`, `data/lacunas.json`)
- **Mapeamento colaborativo**: locais acessíveis cadastrados pela comunidade,
  persistidos em SQLite (`app/db.py`)
- **PDF**: geração do roteiro personalizado com ReportLab (passos, documentos,
  contatos, links clicáveis, base legal e fontes consultadas com data de
  verificação)

## Como rodar

### Atalho (Windows)

Depois da instalação (passos 1 a 3 abaixo), basta dar dois cliques em
**`iniciar.bat`**: ele verifica o Ollama, sobe o servidor e abre o navegador em
`http://localhost:8000`. Para encerrar, feche a janela do terminal.

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
2. Baixe o modelo: `ollama pull llama3.2:3b`
3. Deixe o Ollama rodando (ele já roda como serviço após a instalação, ou use `ollama serve`)

### 4. Subir o servidor

```bash
.venv\Scripts\uvicorn app.main:app --port 8000
```

- Aplicação (frontend): `http://localhost:8000`
- Documentação interativa da API: `http://localhost:8000/docs`

Ao subir, o servidor carrega o modelo do Ollama na memória em segundo plano e o
mantém por `OLLAMA_KEEP_ALIVE` (30 min por padrão), para a primeira pergunta não
pagar o tempo de carga. Para desenvolvimento, `--reload` recarrega o código ao
salvar, mas no Windows ele já travou ao recarregar quando rodado em segundo plano
— nesse caso, encerre e suba de novo manualmente depois de editar.

## Trocando para a Claude API (Anthropic)

Quando quiser mais qualidade/confiabilidade na frase de abertura do chat
(recomendado antes de um piloto real com usuários), edite o `.env`:

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sua_chave_aqui
ANTHROPIC_MODEL=claude-sonnet-5
```

Nenhuma outra mudança de código é necessária — como o modelo só escreve uma
frase curta (o resto vem da base verificada), o ganho da Claude API é mais em
naturalidade do texto do que em confiabilidade do roteiro em si.

## Endpoints principais

- `GET /` — o frontend; `GET /status` — verificação de saúde do servidor
- `POST /chat` — recebe a mensagem da pessoa (+ histórico e o roteiro atual, para
  a conversa evoluir) e devolve a resposta, o roteiro atualizado, perguntas de
  triagem, sugestões, contatos e as fontes usadas
- `GET /base/resumo` — contagem de itens da base e contatos de ajuda imediata
- `POST /roteiro/pdf` — gera o PDF do roteiro a partir do JSON retornado por `/chat`
- `GET /locais` / `POST /locais` — mapeamento colaborativo de locais acessíveis
  (rampas, banheiro adaptado, Braille, espaços de baixo estímulo sensorial, etc.)

## Base de conhecimento

- `data/leis.json` — leis e projetos de lei (federais, estaduais-ES e
  municipais de Serra/Vitória/Vila Velha), com trechos literais e link para o
  texto oficial.
- `data/servicos.json` — serviços públicos (BPC, isenção de IPI/IPVA, passe
  livre, credencial de estacionamento, CIPTEA, CRAS, apoio escolar,
  Defensoria, Disque 100...), com passo a passo oficial, documentos, contatos
  e links.
- `data/contatos.json` — telefones, WhatsApp, endereços e horários dos órgãos,
  incluindo unidades de CRAS por bairro.
- `data/lacunas.json` — perguntas que a base **sabidamente não responde**
  (ex.: lista de escolas/clínicas/locais acessíveis) e o contato de quem pode
  responder, para o assistente ser honesto em vez de inventar.

Todo item tem `verificado_em` (data da conferência) e `fonte_url` (página
oficial de onde a informação saiu). **Isso não substitui revisão jurídica**:
é aqui que a parceria com associações de apoio a PCDs/famílias atípicas
mencionada no projeto entra, validando e ampliando a base continuamente.

### Conferindo a base

```bash
python scripts/verificar_base.py
```

Confere se todos os links da base ainda respondem (sem erro/soft-404) e se os
telefones cadastrados aparecem de fato na página de origem. Itens marcados
"para revisão humana" (ex.: PDF sem `pypdf` instalado, certificado de site com
problema) precisam de conferência manual.

## Limitações conhecidas

- **Sem autenticação:** qualquer pessoa que acesse o servidor pode cadastrar locais
  e marcar um local como verificado (`PATCH /locais/{id}/verificar`). Use apenas
  em rede local/demonstração; proteja esse endpoint antes de expor na internet.
- **Cobertura da base:** município (Vitória, Serra, Vila Velha), tipo de rede
  de ensino e tópicos cobertos são limitados ao que as páginas oficiais
  publicam hoje. Perguntas fora disso caem em `lacunas.json` (resposta
  honesta + contato) ou na resposta padrão de "não encontrei".
- **Modelo local (llama3.2:3b):** escreve só uma frase curta e validada; ainda
  assim pode falhar em gerar uma abertura (nesse caso o chat usa só o texto da
  base). A troca para a Claude API é feita no `.env`.
- **Sem entrada por áudio:** o navegador enviaria o áudio a servidores externos
  (reconhecimento de voz nativo), o que exigiria uma decisão de privacidade antes.
