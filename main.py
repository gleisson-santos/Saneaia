"""
Plataforma de Inteligência Operacional para Saneamento
=====================================================
API Principal - FastAPI

Endpoints:
  /api/solicitacoes     - CRUD e filtros de solicitações
  /api/analytics/*      - KPIs, análises por bairro, temporal, tipo, setor
  /api/agent/*          - Chat, insights, análise NLP
  /api/ml/*             - Predições, re-treinamento, métricas do modelo
  /health               - Health check
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from config.settings import get_settings
from database.connection import test_connection
from api.routes import solicitacoes, agent, predictions, integrations, ml


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown da aplicação."""
    print("=" * 60)
    print("🚀 Plataforma de Inteligência Operacional - Saneamento")
    print("=" * 60)

    # Testar conexão com o banco
    db_ok = test_connection()
    app.state.db_healthy = db_ok

    print(f"📊 Banco de dados: {'✅ Conectado' if db_ok else '❌ Falha'}")
    print(f"🤖 Modelo LLM: {get_settings().openrouter_model}")
    print(f"🌐 Servidor: http://{get_settings().app_host}:{get_settings().app_port}")
    print("=" * 60)

    yield

    print("👋 Servidor encerrado.")


# --- App ---
app = FastAPI(
    title="Plataforma de Inteligência Operacional - Saneamento",
    description=(
        "API para análise inteligente de solicitações de serviço de saneamento. "
        "Integra Machine Learning, NLP e Agente de IA (DeepSeek) para geração "
        "de insights operacionais e recomendações estratégicas."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, restringir ao domínio do dashboard
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files ---
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# --- Rotas ---
app.include_router(solicitacoes.router)
app.include_router(agent.router)
app.include_router(predictions.router)
app.include_router(integrations.router)
app.include_router(ml.router)


# --- Health Check ---
@app.get("/health", tags=["Sistema"])
async def health_check():
    """Verifica saúde da aplicação."""
    settings = get_settings()
    return {
        "status": "healthy",
        "database": getattr(app.state, "db_healthy", False),
        "llm_model": settings.openrouter_model,
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.get("/", tags=["Sistema"])
async def root():
    """Serve o Dashboard."""
    return FileResponse(os.path.join(static_dir, "index.html"))


# --- Entry Point ---
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
