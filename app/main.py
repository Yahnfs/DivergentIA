import logging
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import auth, base, chat, locais, roteiro
from app.services.llm_provider import aquecer_modelo

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Logs do próprio projeto (tamanho do prompt, telefones removidos do texto do modelo etc.) aparecem no terminal.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:     %(name)s: %(message)s")
logging.getLogger("divergentia").setLevel(logging.INFO)

app = FastAPI(
    title="DivergentIA",
    description=(
        "Agente de IA para triagem e guia de acessibilidade/inclusão social: "
        "ajuda PCDs, pessoas neurodivergentes e cuidadores a encontrar direitos, "
        "serviços públicos e locais acessíveis na Grande Vitória (ES)."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def sem_cache(request, chamar_proximo):
    # Em desenvolvimento local o front-end muda a toda hora; sem isso o navegador
    # às vezes mantém um style.css/app.js antigo em cache mesmo após um reload normal.
    resposta = await chamar_proximo(request)
    resposta.headers["Cache-Control"] = "no-cache"
    return resposta


@app.on_event("startup")
def startup() -> None:
    init_db()
    # Em segundo plano: não atrasa a subida do servidor.
    threading.Thread(target=aquecer_modelo, daemon=True).start()


app.include_router(chat.router)
app.include_router(base.router)
app.include_router(roteiro.router)
app.include_router(locais.router)
app.include_router(auth.router)


@app.get("/status")
def status() -> dict:
    return {"status": "ok", "servico": "DivergentIA"}


# O mount em "/" precisa ser o último registro: as rotas da API e do /docs têm prioridade.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
