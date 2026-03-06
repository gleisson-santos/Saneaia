"""Motor de analise profissional - Nivel Infraestrutura."""

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from database.connection import get_supabase_client
from agent.llm_client import get_llm_client
from agent.nlp import batch_analyze, categorize_from_fields, extract_location_from_text
from agent.prompts import ANALYSIS_PROMPT, CHAT_PROMPT, KPI_ANALYSIS_PROMPT


class AgentAnalyzer:
    """Orquestra analise profissional de infraestrutura."""

    def __init__(self):
        self.llm = get_llm_client()
        self.supabase = get_supabase_client()

    def _fetch_all_data(self, limit: int = 5000) -> list[dict]:
        """Busca dados completos para analise."""
        try:
            return self.supabase.get_sync("solicitacoes", {
                "select": "id,ss,os_numero,tipo,especificacao,servico,unidade_os,matricula,setor,bairro,logradouro,observacao,situacao,data_encerramento,data_ultima_tramitacao,localidade",
                "order": "data_encerramento.desc",
                "limit": str(limit),
            })
        except Exception as e:
            print(f"Erro ao buscar dados: {e}")
            return []

    def _detect_hotspots(self, data: list[dict]) -> list[dict]:
        """Detecta pontos criticos: logradouros com 3+ chamados."""
        # Agrupar por logradouro + bairro
        location_groups = defaultdict(list)
        for d in data:
            logr = d.get("logradouro") or d.get("unidade_os") or "N/A"
            bairro = d.get("bairro") or "N/A"
            key = f"{logr}|{bairro}"
            location_groups[key].append(d)

        hotspots = []
        for key, records in location_groups.items():
            if len(records) >= 3:
                logradouro, bairro = key.split("|", 1)
                # Metricas
                matriculas = set(r.get("matricula", "") for r in records if r.get("matricula"))
                servicos = Counter(r.get("servico", "") for r in records)
                tipos = Counter(r.get("tipo", "") for r in records)
                tempos = []
                for r in records:
                    enc = r.get("data_encerramento")
                    tram = r.get("data_ultima_tramitacao")
                    if enc and tram:
                        try:
                            t_enc = datetime.fromisoformat(str(enc).replace("Z", "+00:00")) if isinstance(enc, str) else enc
                            t_tram = datetime.fromisoformat(str(tram).replace("Z", "+00:00")) if isinstance(tram, str) else tram
                            horas = (t_enc - t_tram).total_seconds() / 3600
                            if 0 < horas < 10000:
                                tempos.append(horas)
                        except Exception:
                            pass

                # Categorizar
                obs_combined = " ".join(r.get("observacao", "") or "" for r in records[:10])
                esp_combined = " ".join(r.get("especificacao", "") or "" for r in records[:10])
                cat = categorize_from_fields(
                    tipo=records[0].get("tipo", ""),
                    especificacao=esp_combined,
                    observacao=obs_combined,
                )

                hotspots.append({
                    "logradouro": logradouro,
                    "bairro": bairro,
                    "setor": records[0].get("setor", ""),
                    "unidade_os": records[0].get("unidade_os", ""),
                    "total_chamados": len(records),
                    "matriculas_afetadas": len(matriculas),
                    "servicos": dict(servicos.most_common(3)),
                    "tipos_problema": dict(tipos.most_common(3)),
                    "tempo_medio_horas": round(sum(tempos) / len(tempos), 1) if tempos else None,
                    "categoria_tecnica": cat["label"],
                })

        hotspots.sort(key=lambda x: x["total_chamados"], reverse=True)
        return hotspots[:20]

    def _analyze_reincidence(self, data: list[dict]) -> dict:
        """Deep-dive de reincidencia por matricula."""
        # Agrupar por matricula
        by_matricula = defaultdict(list)
        for d in data:
            m = d.get("matricula")
            if m and m != "nan" and m != "None":
                by_matricula[m].append(d)

        chronic = []  # 3+ chamados
        palliative_suspects = []  # Resolvido rapido + reincidencia

        for matricula, records in by_matricula.items():
            if len(records) >= 3:
                # Ordenar por data
                dated = []
                for r in records:
                    enc = r.get("data_encerramento")
                    if enc:
                        try:
                            dt = datetime.fromisoformat(str(enc).replace("Z", "+00:00")) if isinstance(enc, str) else enc
                            dated.append((dt, r))
                        except Exception:
                            pass

                dated.sort(key=lambda x: x[0])

                # Verificar intervalo entre chamados
                intervals = []
                for i in range(1, len(dated)):
                    diff = (dated[i][0] - dated[i-1][0]).days
                    intervals.append(diff)

                avg_interval = sum(intervals) / len(intervals) if intervals else 999
                min_interval = min(intervals) if intervals else 999

                tipos = Counter(r.get("tipo", "") for r in records)

                chronic.append({
                    "matricula": matricula,
                    "total_chamados": len(records),
                    "bairro": records[0].get("bairro", ""),
                    "unidade_os": records[0].get("unidade_os", ""),
                    "tipos": dict(tipos.most_common(3)),
                    "intervalo_medio_dias": round(avg_interval, 1),
                    "menor_intervalo_dias": min_interval,
                    "alerta_falha_definitiva": avg_interval < 90,
                })

                # Detectar reparo paliativo: resolucao rapida + reincidencia < 7 dias
                if min_interval <= 7:
                    palliative_suspects.append({
                        "matricula": matricula,
                        "bairro": records[0].get("bairro", ""),
                        "unidade_os": records[0].get("unidade_os", ""),
                        "reincidencia_dias": min_interval,
                        "total_chamados": len(records),
                        "tipo": records[0].get("tipo", ""),
                    })

        chronic.sort(key=lambda x: x["total_chamados"], reverse=True)
        palliative_suspects.sort(key=lambda x: x["reincidencia_dias"])

        return {
            "total_matriculas_reinicidentes": len(chronic),
            "cronicas_top15": chronic[:15],
            "reparos_paliativos": palliative_suspects[:10],
            "taxa_reincidencia": round(len(chronic) / len(by_matricula) * 100, 1) if by_matricula else 0,
        }

    def _get_technical_categories(self, data: list[dict]) -> dict:
        """Categoriza todos os problemas tecnicamente."""
        categories = Counter()
        for d in data:
            cat = categorize_from_fields(
                tipo=d.get("tipo", ""),
                especificacao=d.get("especificacao", ""),
                observacao=d.get("observacao", ""),
            )
            categories[cat["label"]] += 1

        total = sum(categories.values()) or 1
        return {
            cat: {"total": count, "percentual": round(count / total * 100, 1)}
            for cat, count in categories.most_common()
        }

    def _get_kpis(self) -> dict:
        """Busca KPIs."""
        try:
            data = self.supabase.get_sync("kpis_gerais")
            return data[0] if data else {}
        except Exception:
            return {}

    async def generate_insights(self) -> str:
        """Gera insights profissionais com analise completa."""
        data = self._fetch_all_data()
        if not data:
            return "Sem dados disponiveis para analise."

        # Analises profundas
        hotspots = self._detect_hotspots(data)
        reincidence = self._analyze_reincidence(data)
        tech_categories = self._get_technical_categories(data)

        # NLP nas observacoes
        observations = [d.get("observacao", "") for d in data if d.get("observacao")]
        nlp_results = batch_analyze(observations) if observations else {}

        # ML predictions
        ml_summary = []
        try:
            ml_summary = self.supabase.get_sync("predicoes_ml", {
                "select": "classificacao_prevista,score_prioridade,probabilidade_reincidencia",
                "limit": "100",
                "order": "created_at.desc",
            })
        except Exception:
            pass

        # KPIs agregados
        kpis = self._get_kpis()

        # Montar prompt
        prompt = ANALYSIS_PROMPT.format(
            aggregated_data=json.dumps(kpis, ensure_ascii=False, default=str),
            hotspots=json.dumps(hotspots[:10], ensure_ascii=False, default=str),
            reincidence_data=json.dumps(reincidence, ensure_ascii=False, default=str),
            palliative_repairs=json.dumps(reincidence.get("reparos_paliativos", []), ensure_ascii=False, default=str),
            technical_categories=json.dumps(tech_categories, ensure_ascii=False, default=str),
            ml_predictions=json.dumps(ml_summary[:20], ensure_ascii=False, default=str),
            nlp_analysis=json.dumps(nlp_results, ensure_ascii=False, default=str),
        )

        response = await self.llm.chat(prompt, temperature=0.2, max_tokens=6000)
        return response

    async def generate_and_save_insights(self) -> list[dict]:
        """Gera e salva insights."""
        raw = await self.generate_insights()
        insight_data = {
            "tipo_insight": "ANALISE_INFRAESTRUTURA",
            "titulo": "Analise Operacional Profissional",
            "descricao": raw,
            "nivel_criticidade": "ALTO",
            "recomendacao": "",
            "ativo": True,
        }
        try:
            return await self.supabase.post("insights_ia", insight_data)
        except Exception as e:
            print(f"Erro ao salvar: {e}")
            return [insight_data]

    async def chat(self, user_query: str) -> str:
        """Chat com contexto profissional."""
        data = self._fetch_all_data(limit=2000)
        kpis = self._get_kpis()
        hotspots = self._detect_hotspots(data) if data else []
        reincidence = self._analyze_reincidence(data) if data else {}

        recent_insights = "Nenhum."
        try:
            ins = await self.supabase.get("insights_ia", {
                "ativo": "eq.true", "order": "created_at.desc",
                "limit": "2", "select": "titulo,descricao,created_at",
            })
            if ins:
                recent_insights = json.dumps(ins, ensure_ascii=False, default=str)[:3000]
        except Exception:
            pass

        prompt = CHAT_PROMPT.format(
            data_summary=json.dumps(kpis, ensure_ascii=False, default=str),
            hotspots_summary=json.dumps(hotspots[:5], ensure_ascii=False, default=str),
            reincidence_summary=json.dumps({
                "total_reinicidentes": reincidence.get("total_matriculas_reinicidentes", 0),
                "taxa": reincidence.get("taxa_reincidencia", 0),
                "top3": reincidence.get("cronicas_top15", [])[:3],
            }, ensure_ascii=False, default=str),
            recent_insights=recent_insights,
            user_query=user_query,
        )

        response = await self.llm.chat(prompt, temperature=0.3)

        try:
            await self.supabase.post("agent_conversations", {
                "user_query": user_query,
                "agent_response": response,
                "context_data": {"kpis": kpis},
            })
        except Exception:
            pass

        return response

    async def analyze_kpis(self) -> str:
        """Analise executiva com foco em infraestrutura."""
        data = self._fetch_all_data(limit=3000)
        kpis = self._get_kpis()
        hotspots = self._detect_hotspots(data) if data else []
        reincidence = self._analyze_reincidence(data) if data else {}

        try:
            temporal = self.supabase.get_sync("analise_temporal", {
                "order": "ano.asc,mes_numero.asc",
            })
        except Exception:
            temporal = []

        prompt = KPI_ANALYSIS_PROMPT.format(
            kpis=json.dumps(kpis, ensure_ascii=False, default=str),
            trends=json.dumps(temporal, ensure_ascii=False, default=str),
            hotspots=json.dumps(hotspots[:10], ensure_ascii=False, default=str),
            reincidence_kpis=json.dumps({
                "total_reinicidentes": reincidence.get("total_matriculas_reinicidentes", 0),
                "taxa_reincidencia": reincidence.get("taxa_reincidencia", 0),
                "reparos_paliativos": len(reincidence.get("reparos_paliativos", [])),
            }, ensure_ascii=False, default=str),
        )

        return await self.llm.chat(prompt, temperature=0.2)


    async def analyze_single_demand(self, matricula: str, logradouro: str, observacao: str = "") -> dict:
        """Faz a análise cirúrgica preditiva de UMA demanda para o Dashboard Externo (Gestão UMB)."""
        print(f"🔍 [DEBUG] Analisando: Matrícula='{matricula}', Logradouro='{logradouro}', Obs='{observacao[:30]}...' ")
        historico_logradouro = []
        historico_matricula = []
        
        # Limpeza do logradouro para busca mais flexível
        search_term = logradouro
        # Trata hífen normal, meia-risca (–) e trava-risca (—)
        import re
        if re.search(r' [-–—] ', logradouro):
            search_term = re.split(r' [-–—] ', logradouro)[0]
        
        # Remove números iniciais ou prefixos comuns se existirem (ex: "123 - RUA...")
        search_term = re.sub(r'^\d+\s*[-–—]\s*', '', search_term).strip()
        print(f"🔍 [DEBUG] Termo de busca final: '{search_term}'")
        
        async def fetch_logradouro():
            if search_term and len(search_term) > 3:
                return await self.supabase.get(
                    "solicitacoes", 
                    {"logradouro": f"ilike.%{search_term}%", "limit": "100"}
                )
            return []

        async def fetch_matricula():
            if matricula and matricula not in ["nan", "None", ""]:
                return await self.supabase.get(
                    "solicitacoes", 
                    {"matricula": f"eq.{matricula}", "limit": "50"}
                )
            return []

        import asyncio
        import time
        t_start = time.time()
        try:
            historico_logradouro, historico_matricula = await asyncio.gather(
                fetch_logradouro(),
                fetch_matricula(),
                return_exceptions=True
            )
            if isinstance(historico_logradouro, Exception):
                print(f"Erro DB Logradouro: {historico_logradouro}")
                historico_logradouro = []
            if isinstance(historico_matricula, Exception):
                print(f"Erro DB Matricula: {historico_matricula}")
                historico_matricula = []
        except Exception as e:
            print(f"Erro no gather do DB: {e}")
        print(f"🔍 [DEBUG] Buscas no DB concluídas em {time.time()-t_start:.2f}s")

            
        q_logr = len(historico_logradouro)
        q_mat = len(historico_matricula)
        
        # Filtros de tempo detalhados (6 meses, 12 meses, 24 meses) / Matrícula e Logradouro
        now = datetime.now(timezone.utc)
        q_mat_6m = 0
        q_mat_12m = 0
        q_mat_24m = 0
        q_mat_total = len(historico_matricula)
        
        q_logr_6m = 0 # Novos dados por logradouro
        
        last_req_date = None
        
        def parse_date(d_str):
            if not d_str: return None
            try:
                if isinstance(d_str, str):
                    val = d_str.replace("Z", "+00:00")
                    enc = datetime.fromisoformat(val)
                else:
                    enc = d_str
                if enc.tzinfo is None:
                    enc = enc.replace(tzinfo=timezone.utc)
                else:
                    enc = enc.astimezone(timezone.utc)
                return enc
            except:
                return None

        # Processa Matricula
        for r in historico_matricula:
            enc = parse_date(r.get("data_encerramento") or r.get("created_at") or r.get("data_inicio"))
            if enc:
                diff_days = (now - enc).days
                if diff_days <= 180: q_mat_6m += 1
                if diff_days <= 365: q_mat_12m += 1
                if diff_days <= 730: q_mat_24m += 1
                if last_req_date is None or enc > last_req_date:
                    last_req_date = enc

        # Processa Logradouro (6 meses)
        for r in historico_logradouro:
            enc = parse_date(r.get("data_encerramento") or r.get("created_at") or r.get("data_inicio"))
            if enc:
                if (now - enc).days <= 180:
                    q_logr_6m += 1
        
        # 🚨 Regras de Negócio: Definição do Nível de Atenção Operacional (Weighted Recency)
        # Níveis: SITUAÇÃO REGULAR, ATENÇÃO REDOBRADA, ALERTA CRÍTICO
        nivel_badge = "SITUAÇÃO REGULAR"
        
        if q_mat_6m >= 3:
            # Reincidência muito alta no curto prazo
            nivel_badge = "ALERTA CRÍTICO"
            badge_text = f"ALERTA OPERACIONAL: Alta frequência nos últimos 6 meses ({q_mat_6m} chamados)"
        elif q_mat_6m >= 1 or q_mat_12m >= 2:
            # Atividade recente que exige cuidado
            nivel_badge = "ATENÇÃO REDOBRADA"
            badge_text = f"ATENÇÃO REDOBRADA: Atividade recente detectada na matrícula"
        elif q_mat_total >= 5:
            # Passado volumoso mas presente tranquilo
            nivel_badge = "OBSERVAÇÃO"
            badge_text = f"OBSERVAÇÃO: Endereço com {q_mat_total} chamados históricos (Monitorar Infraestrutura)"
        else:
            badge_text = "Nenhuma anomalia técnica ou recente detectada."
            
        # 🤖 ML Score Simulado/Heurístico (Recency-First)
        # Se não há chamados nos últimos 12 meses, o risco é drasticamente reduzido
        if q_mat_12m == 0 and q_mat_total > 0:
            # Base residual para histórico antigo (máximo 25%)
            base_risk = min(10 + (q_mat_total * 0.5), 25) 
        else:
            base_risk = 10
            base_risk += (q_mat_6m * 40)    # Peso forte para reincidência direta
            base_risk += (q_mat_12m * 15)   # Histórico anual do cliente
            
            # 🏢 Logradouro (Vizinhança): Contribuição controlada para evitar falsos positivos em ruas grandes
            # Se a matrícula está limpa (q_mat_12m == 0), a rua contribui com no máximo 20%
            # Se a matrícula já tem histórico, a rua pode elevar o risco em até 40%
            area_cap = 40 if q_mat_12m > 0 else 20
            area_contribution = min(q_logr * 0.5, area_cap)
            base_risk += area_contribution
            
        score_ml = min(base_risk, 98)
            
        # 🧠 Chamada Real ao Modelo de IA (Grok OpenRouter)
        # Enriquecendo o prompt com os novos dados temporais e observação do usuário
        last_date_str = last_req_date.strftime("%d/%m/%Y") if last_req_date else "Não identificada"
        
        prompt = f"""
        Você é a IA de diagnóstico operacional e engenharia do SanealA.
        Uma nova demanda de FALTA DE ÁGUA acabou de ser sinalizada para o Teto: {logradouro} (Matrícula: {matricula}).
        
        DADOS DE SUPORTE:
        - Última solicitação desta matrícula: {last_date_str}
        - Chamados (Matrícula) nos últimos 6 meses: {q_mat_6m}
        - Chamados (Matrícula) nos últimos 12 meses: {q_mat_12m}
        - Chamados (Matrícula) nos últimos 24 meses: {q_mat_24m}
        - Total Histórico na Matrícula: {q_mat_total}
        - Chamados totais no logradouro: {q_logr}
        - Probabilidade Máquina (ML) de Reincidência: {score_ml}%
        
        OBSERVAÇÃO DO USUÁRIO: "{observacao}"
        
        TAREFA:
        1. Escreva 1 parágrafo (máx 3 frases) com o "Insight Técnico da IA" focado na infraestrutura.
        2. Analise o SENTIMENTO e ESTADO EMOCIONAL do usuário com base na observação acima.
        Seja técnico e objetivo. 
        
        FORMATO DE RESPOSTA (Obrigatório):
        INSIGHT: [Seu insight aqui]
        SENTIMENTO: [Emoji + Curta descrição do estado emocional: Irritado, Calmo, Crítico, Conformado, Impaciente]
        """
        
        insight_text = "Análise preliminar indica ausência de padrão crônico severo. Recomendado atendimento de praxe."
        sentiment_text = "⚪ Neutro"
        
        if score_ml > 30 or q_mat > 0 or q_logr > 3 or observacao:
            try:
                raw_response = await self.llm.chat(prompt, temperature=0.1, max_tokens=350)
                # Parse simples da resposta estruturada
                if "INSIGHT:" in raw_response and "SENTIMENTO:" in raw_response:
                    parts = raw_response.split("SENTIMENTO:")
                    insight_text = parts[0].replace("INSIGHT:", "").strip().replace("*", "")
                    sentiment_text = parts[1].strip().replace("*", "")
                else:
                    insight_text = raw_response.replace("*", "").strip()
            except Exception as e:
                print(f"Erro no fechamento do LLM para a demanda unica: {e}")
            
        return {
            "risco_nivel": nivel_badge,
            "risco_alerta": badge_text,
            "historico_local": f"{q_logr} chamados registrados nos últimos anos neste logradouro.",
            "ml_score_probabilidade": score_ml,
            "insight_tecnico": insight_text,
            "sentiment_diagnosis": sentiment_text,
            "q_mat_total": q_mat_total,
            "q_logr": q_logr,
            "q_logr_6m": q_logr_6m,
            "q_mat_6m": q_mat_6m,
            "q_mat_12m": q_mat_12m,
            "q_mat_24m": q_mat_24m,
            "last_req_date": last_date_str,
            "timestamp": now.isoformat()
        }


def get_analyzer() -> AgentAnalyzer:
    return AgentAnalyzer()
