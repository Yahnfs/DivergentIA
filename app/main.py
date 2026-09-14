from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import chat, locais, roteiro

app = FastAPI(
    title="DivergentIA",
    description=(
        "Agente de IA para triagem e guia de acessibilidade/inclusão social: "
        "ajuda PCDs, pessoas neurodivergentes e cuidadores a encontrar direitos, "
        "serviços públicos e locais acessíveis na Grande Vitória (ES)."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(chat.router)
app.include_router(roteiro.router)
app.include_router(locais.router)


@app.get("/")
def raiz() -> dict:
    return {"status": "ok", "servico": "DivergentIA"}
