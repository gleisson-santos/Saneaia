"""Rotas de solicitações e analytics."""

from fastapi import APIRouter, Query
from typing import Optional
from database.connection import get_supabase_client

router = APIRouter(prefix="/api", tags=["Solicitações & Analytics"])


@router.get("/solicitacoes")
async def list_solicitacoes(
    bairro: Optional[str] = None,
    tipo: Optional[str] = None,
    situacao: Optional[str] = None,
    setor: Optional[str] = None,
    localidade: Optional[str] = None,
    logradouro: Optional[str] = None,
    servico: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Lista solicitacoes com filtros opcionais."""
    supabase = get_supabase_client()

    params = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
        "offset": str(offset),
    }

    if bairro:
        params["bairro"] = f"ilike.%{bairro}%"
    if tipo:
        params["tipo"] = f"ilike.%{tipo}%"
    if situacao:
        params["situacao"] = f"ilike.%{situacao}%"
    if setor:
        params["setor"] = f"ilike.%{setor}%"
    if localidade:
        params["localidade"] = f"ilike.%{localidade}%"
    if logradouro:
        params["logradouro"] = f"ilike.%{logradouro}%"
    if servico:
        params["servico"] = f"ilike.%{servico}%"

    data = await supabase.get("solicitacoes", params)
    return {"data": data, "count": len(data), "limit": limit, "offset": offset}


@router.get("/solicitacoes/{solicitacao_id}")
async def get_solicitacao(solicitacao_id: str):
    """Busca uma solicitacao especifica."""
    supabase = get_supabase_client()
    data = await supabase.get("solicitacoes", {"id": f"eq.{solicitacao_id}"})
    if not data:
        return {"error": "Solicitacao nao encontrada"}
    return {"data": data[0]}


# -------------------------------------------------------
# Analytics
# -------------------------------------------------------
@router.get("/analytics/kpis")
async def get_kpis():
    """Retorna KPIs gerais do sistema."""
    supabase = get_supabase_client()
    data = await supabase.get("kpis_gerais")
    return {"data": data[0] if data else {}}


@router.get("/analytics/bairros-criticos")
async def get_analytics_bairros_criticos(
    limit: int = Query(default=10, ge=1, le=100),
    ano: Optional[int] = None,
):
    """Retorna os bairros com maiores indices de reincidencia e insatisfacao (Falta de agua, Vazamentos, Reclamacoes)."""
    supabase = get_supabase_client()
        
    # Agregação raw dinâmica para suportar metricas de cruzamento e filtro temporal
    data = await supabase.get("solicitacoes", {
        "select": "bairro, matricula, servico, created_at",
        "limit": "100000",
    })
    
    from collections import defaultdict, Counter
    target_year = str(ano) if ano else None
    
    bairros_score = Counter()
    matriculas_por_bairro = defaultdict(list)
    bairro_insatisfacao = Counter()
    
    # Palavras-chave associadas a insatisfação do cliente (esgoto, falta d'agua, vazamento)
    keywords = ["FALTA AGUA", "VAZ", "RECL", "QUALIDADE", "RETORNO", "DESOBS"]
    
    for d in data:
        if target_year:
            c_at = d.get("created_at", "")
            if not c_at or not c_at.startswith(target_year):
                continue
                
        b = d.get("bairro") or "Sem Bairro"
        mat = d.get("matricula")
        srv = str(d.get("servico", "")).upper()
        
        # 1. Contabiliza matrículas para cálculo de reincidência
        if mat:
            matriculas_por_bairro[b].append(mat)
            
        # 2. Contabiliza se o seviço é de natureza crítica/insatisfatória
        if any(k in srv for k in keywords):
            bairro_insatisfacao[b] += 1
            
    # Processa métricas
    for b, mats in matriculas_por_bairro.items():
        count_mats = Counter(mats)
        # Uma reincidência é quando uma mesma matrícula tem 2 ou mais demandas
        reincidencias = sum(1 for count in count_mats.values() if count > 1)
        
        # Peso do Índice Crítico: Reincidências pesam o dobro
        score = (reincidencias * 2) + bairro_insatisfacao[b]
        bairros_score[b] = score
        
    result = [{"bairro": k, "indice_critico": v} for k, v in bairros_score.most_common(limit)]
    return {"data": result}


@router.get("/analytics/por-logradouro")
async def get_analytics_por_logradouro(
    limit: int = Query(default=30, ge=1, le=200),
    bairro: Optional[str] = None,
):
    """Analise de solicitacoes por logradouro."""
    supabase = get_supabase_client()
    params = {
        "order": "total_solicitacoes.desc",
        "limit": str(limit),
    }
    if bairro:
        params["bairro"] = f"ilike.%{bairro}%"
    data = await supabase.get("analise_por_logradouro", params)
    return {"data": data}


@router.get("/analytics/pontos-criticos")
async def get_pontos_criticos(
    limit: int = Query(default=30, ge=1, le=100),
    bairro: Optional[str] = None,
):
    """Pontos criticos: logradouros com 3+ chamados."""
    supabase = get_supabase_client()
    params = {
        "order": "total_chamados.desc",
        "limit": str(limit),
    }
    if bairro:
        params["bairro"] = f"ilike.%{bairro}%"
    data = await supabase.get("pontos_criticos_logradouro", params)
    return {"data": data}


@router.get("/analytics/por-servico")
async def get_analytics_por_servico():
    """Analise de solicitacoes por tipo de servico."""
    supabase = get_supabase_client()
    data = await supabase.get("analise_por_servico", {
        "order": "total_solicitacoes.desc",
    })
    return {"data": data}


@router.get("/analytics/temporal")
async def get_analytics_temporal():
    """Analise temporal de solicitacoes."""
    supabase = get_supabase_client()
    data = await supabase.get("analise_temporal", {
        "order": "ano.asc,mes_numero.asc",
    })
    return {"data": data}


@router.get("/analytics/por-tipo")
async def get_analytics_por_tipo():
    """Analise de solicitacoes por tipo."""
    supabase = get_supabase_client()
    data = await supabase.get("solicitacoes", {
        "select": "tipo",
        "limit": "10000",
    })
    from collections import Counter
    tipos = Counter(d.get("tipo", "") for d in data)
    result = [{"tipo": k, "total": v} for k, v in tipos.most_common()]
    return {"data": result}


@router.get("/analytics/por-setor")
async def get_analytics_por_setor():
    """Analise de solicitacoes por setor."""
    supabase = get_supabase_client()
    data = await supabase.get("solicitacoes", {
        "select": "setor",
        "limit": "100000",
    })
    from collections import Counter
    setores = Counter(d.get("setor", "") for d in data)
    result = [{"setor": k, "total": v} for k, v in setores.most_common()]
    return {"data": result}


@router.get("/analytics/reincidencia")
async def get_reincidencia(min_solicitacoes: int = Query(default=3, ge=2)):
    """Clientes com reincidencia (multiplas solicitacoes)."""
    supabase = get_supabase_client()
    data = await supabase.get("reincidencia_matricula", {
        "order": "total_chamados.desc",
        "limit": "50",
    })
    return {"data": data}


@router.get("/analytics/mapa-calor-setor")
async def get_mapa_calor_setor():
    """Hierarquia de solicitacoes: Setor -> Bairro para Mapa de Calor."""
    supabase = get_supabase_client()
    data = await supabase.get("solicitacoes", {
        "select": "setor, bairro",
        "limit": "100000",
    })
    
    # Aggregation logic
    from collections import defaultdict
    setores = defaultdict(lambda: defaultdict(int))
    for d in data:
        s = d.get("setor") or "DESCONHECIDO"
        b = d.get("bairro") or "Sem Bairro"
        setores[s][b] += 1
        
    result = []
    for s, bairros_dict in setores.items():
        total_setor = sum(bairros_dict.values())
        bairros_list = [
            {"bairro": b, "total": t}
            for b, t in sorted(bairros_dict.items(), key=lambda x: x[1], reverse=True)[:10] # Top 10 bairros per sector to prevent UI clutter
        ]
        result.append({
            "setor": s,
            "total": total_setor,
            "bairros": bairros_list
        })
        
    # Sort sectors by total volume
    result.sort(key=lambda x: x["total"], reverse=True)
    return {"data": result[:15]} # Top 15 sectors

