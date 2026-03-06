"""Rotas de integração externa (Webhooks para Dashboards como Lovable)."""

import traceback
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from agent.analyzer import get_analyzer

router = APIRouter(prefix="/api/integrations", tags=["Integrações Externas"])

class ExternalDemand(BaseModel):
    id: str  # UID da demanda
    matricula: Optional[str] = None
    logradouro: str
    bairro: Optional[str] = None
    numero_os: Optional[str] = None
    observacao: Optional[str] = None

class ExternalDemandsPayload(BaseModel):
    demandas: List[ExternalDemand]

@router.post("/analyze-external-demands")
async def analyze_external_demands(raw_payload: dict):
    """
    Recebe uma lista de demandas de falta de água do Gestão UMB e retorna um insight preditivo para cada.
    """
    import logging
    import re
    import asyncio
    
    # Log super detalhado para depuração
    print(f"📥 [INTEGRATION RAW] Payload recebido no servidor: {raw_payload}")
    
    try:
        # Tenta extrair a lista de demandas do dicionário
        demandas_raw = raw_payload.get("demandas", [])
        if not demandas_raw:
             # Tenta ver se veio a lista diretamente
             if isinstance(raw_payload, list):
                 demandas_raw = raw_payload
             else:
                 print("⚠️ [WARNING] Nenhuma demanda encontrada no payload")
        
        analyzer = get_analyzer()
        
        # Controle de amostragem por logradouro no lote
        logrados_count = {}
        
        async def process_demand(d: dict):
            # Extração flexível de campos
            d_id = str(d.get("id", "0"))
            
            # 1. PRIORIDADE: Campo 'matricula' nativo (Lovable já envia agora)
            m = d.get("matricula")
            logr = d.get("logradouro") or d.get("logr") or ""
            obs = d.get("observacao") or ""
            
            # 2. SEGURANÇA: Só tenta Regex se a matrícula nativa estiver vazia
            if not m or m in ["nan", "None", ""]:
                match = re.search(r'MATRICULA:\s*(\d+)', obs, re.IGNORECASE)
                if match:
                    m = match.group(1)
            
            # 3. AMOSTRAGEM DE LOTE (Max 2 por logradouro)
            # Normalizamos o logr para contagem (sem números de casa se houver)
            logr_norm = re.sub(r'\d+', '', logr).strip().upper()
            logrados_count[logr_norm] = logrados_count.get(logr_norm, 0) + 1
            
            # Se já analisamos o suficiente desta rua neste lote, retornamos insight resumido
            if logrados_count[logr_norm] > 2:
                return {
                    "id": d_id,
                    "matricula": m,
                    "logradouro": logr,
                    "ai_recomendacao": "ℹ️ REINCIDÊNCIA EM LOTE: Este logradouro já possui múltiplas ocorrências neste agrupamento. Consulte as primeiras análises do logradouro para detalhes técnicos completos.",
                    "chance_reincidencia": 50,
                    "logradouro_historico": "Múltiplas demandas no mesmo trecho.",
                    "risco_nivel": "MEDIO",
                    "risco_alerta": "ALERTA DE BATCH: Alta concentração momentânea na rua.",
                    "sentimento": "⚪ Coletivo"
                }

            insight = await analyzer.analyze_single_demand(
                matricula=str(m or ""),
                logradouro=logr,
                observacao=obs
            )
            
            # --- Relatório Técnico Estruturado (Recency-First) ---
            score = insight.get("ml_score_probabilidade", 0)
            q_total = insight.get("q_mat_total", 0)
            q_24m = insight.get("q_mat_24m", 0)
            q_12m = insight.get("q_mat_12m", 0)
            q_6m = insight.get("q_mat_6m", 0)
            q_l6m = insight.get("q_logr_6m", 0) # Logradouro 6m
            last_date = insight.get("last_req_date", "Não identificada")
            sentiment = insight.get("sentiment_diagnosis", "⚪ Não avaliado")
            
            # Montagem do Report Rico (Interativo e Informativo)
            p_insight = (
                f"📊 HISTÓRICO DE SOLICITAÇÕES:\n"
                f"• Total histórico (3+ anos): {q_total} solicitações\n"
                f"• Acumulado nos últimos 12 meses: {q_12m}\n"
                f"• Recorrência direta nos últimos 6 meses: {q_6m}\n\n"
                f"📍 ANÁLISE DO LOGRADOURO:\n"
                f"• Este logradouro teve uma taxa de {q_l6m} reclamações nos últimos 6 meses.\n"
                f"📅 Última abertura: {last_date}\n\n"
                f"🚩 ESTADO DO CLIENTE: {sentiment}\n\n"
                f"Insight técnico | Atenção:\n"
            )
            
            if score > 75 and q_6m > 0:
                p_insight += f"> ALERTA CRÍTICO: Probabilidade de {score}% de recorrência direta. O volume na matrícula ({q_6m} nos últimos 6 meses) confirma falha crônica ativa. Prioridade máxima para varredura geofônica."
            elif q_6m > 0:
                p_insight += f"> ATENÇÃO REDOBRADA: Recorrência detectada recentemente ({q_6m} chamados). Verifique se houve manobras de rede ou problemas de pressão que possam estar afetando o ramal."
            elif score > 50 and q_l6m > 10:
                p_insight += f"> ALERTA POR LOGRADOURO: Atenção moderada ({score}%) devido ao volume na rua ({q_l6m} em 6 meses). Embora esta matrícula esteja estável, a região apresenta sinais de instabilidade."
            elif q_total >= 5 and q_12m == 0:
                p_insight += f"> ANÁLISE DE PASSIVO: Matrícula com {q_total} solicitações históricas, mas sem ocorrências recentes. Monitorar integridade da tubulação devido à idade da infraestrutura."
            else:
                p_insight += "> SITUAÇÃO REGULAR: Sem padrões de recorrência anômala identificados para esta matrícula. Siga com o protocolo de atendimento padrão."

            # Mapeamento para o Lovable
            return {
                "id": d_id,
                "matricula": m,
                "logradouro": logr,
                "ai_recomendacao": p_insight,
                "chance_reincidencia": score,
                "logradouro_historico": insight.get("historico_local"),
                "risco_nivel": insight.get("risco_nivel"),
                "risco_alerta": insight.get("risco_alerta"),
                "sentimento": sentiment
            }

        tasks = [process_demand(d) for d in demandas_raw]
        resultados = await asyncio.gather(*tasks)

        print(f"✅ [DEBUG] Devolvendo resultados: {resultados}")
        logging.info(f"✅ Lote processado com sucesso. Devolvendo {len(resultados)} análises.")
        return {"status": "success", "analises": resultados}
    except Exception as e:
        print(f"❌ Erro na integração externa: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
