"""Rotas do Agente de IA (insights, chat, análises)."""

import traceback
from fastapi import APIRouter
from api.models import ChatRequest, ChatResponse
from agent.analyzer import get_analyzer
from agent.nlp import batch_analyze
from database.connection import get_supabase_client

router = APIRouter(prefix="/api/agent", tags=["Agente IA"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Chat interativo com o agente de IA."""
    try:
        analyzer = get_analyzer()
        response = await analyzer.chat(request.query)
        return ChatResponse(response=response)
    except Exception as e:
        print(f"❌ Erro no chat: {e}")
        traceback.print_exc()
        return ChatResponse(response=f"Erro ao processar: {str(e)}")


@router.post("/analyze")
async def run_analysis():
    """Executa análise completa e gera insights."""
    try:
        analyzer = get_analyzer()
        response = await analyzer.generate_insights()
        return {"insights": response}
    except Exception as e:
        print(f"❌ Erro na análise: {e}")
        traceback.print_exc()
        return {"insights": f"Erro ao gerar insights: {str(e)}"}


@router.post("/analyze-and-save")
async def run_analysis_and_save():
    """Executa análise completa, gera e salva insights no banco."""
    analyzer = get_analyzer()
    saved = await analyzer.generate_and_save_insights()
    return {"saved": saved}


@router.get("/insights")
async def list_insights(limit: int = 10):
    """Lista insights gerados pela IA."""
    supabase = get_supabase_client()
    data = await supabase.get("insights_ia", {
        "order": "created_at.desc",
        "limit": str(limit),
        "ativo": "eq.true",
    })
    return {"data": data}


@router.post("/analyze-kpis")
async def analyze_kpis():
    """Gera análise executiva dos KPIs."""
    analyzer = get_analyzer()
    response = await analyzer.analyze_kpis()
    return {"analysis": response}


@router.get("/nlp-summary")
async def get_nlp_summary(limit: int = 500):
    """Retorna resumo da análise NLP das observações."""
    supabase = get_supabase_client()
    data = supabase.get_sync("solicitacoes", {
        "select": "observacao",
        "observacao": "not.is.null",
        "order": "created_at.desc",
        "limit": str(limit),
    })
    observations = [d["observacao"] for d in data if d.get("observacao")]
    summary = batch_analyze(observations)
    return {"data": summary}


@router.get("/conversations")
async def list_conversations(limit: int = 20):
    """Lista histórico de conversas com o agente."""
    supabase = get_supabase_client()
    data = await supabase.get("agent_conversations", {
        "order": "created_at.desc",
        "limit": str(limit),
    })
    return {"data": data}
