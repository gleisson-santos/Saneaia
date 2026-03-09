import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from database.connection import get_supabase_client

class HydraulicClusterer:
    """Motor de Clustering Espaço-Temporal para detecção de Causa Raiz."""

    def __init__(self):
        self.supabase = get_supabase_client()
        # Palavras-chave de criticidade técnica
        self.critical_services = ["FALTA AGUA", "VAZAMENTO", "ESGOTO", "QUALIDADE", "PRES-BAIXA"]

    async def get_recent_data(self, hours=48):
        """Busca dados recentes para análise de clusters."""
        # Calculando data gte no formato Supabase (ISO)
        since_date = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        # Usamos a view de análise que já tem o ano e mês tratados
        params = [
            ("select", "id, matricula, logradouro, bairro, setor, servico, created_at, situacao"),
            ("created_at", f"gte.{since_date}"),
            ("limit", "1000")
        ]
        return await self.supabase.get("solicitacoes", params)

    def detect_events(self, data):
        """
        Agrupa solicitações em Eventos Mestres ou diagnósticos isolados.
        Retorna uma lista de dicionários de eventos.
        """
        clusters = defaultdict(list)
        
        # 1. Agrupamento Espacial por Logradouro + Setor
        for d in data:
            key = (d.get("setor"), d.get("logradouro"))
            clusters[key].append(d)
            
        events = []
        
        for (setor, logradouro), demands in clusters.items():
            count = len(demands)
            
            # Caso A: Evento Mestre (Cluster de massa)
            if count >= 3:
                # Identifica o serviço predominante
                srv_counts = Counter([str(d.get("servico", "")).upper() for d in demands])
                main_srv = srv_counts.most_common(1)[0][0]
                
                # DNA da Falha: Se houver Falta d'agua + Vazamento no mesmo setor/logradouro
                signature = "Falha em Rede de Distribuição" if "VAZ" in str(srv_counts) and "FALTA" in str(srv_counts) else "Manutenção Programada ou Obstrução Local"
                
                events.append({
                    "type": "MASTER_EVENT",
                    "severity": "CRITICAL" if count > 5 else "WARNING",
                    "description": f"Evento Hidráulico Mestre no Logradouro {logradouro}",
                    "impact": f"{count} matrículas afetadas",
                    "probable_cause": signature,
                    "location": f"{logradouro} ({setor})",
                    "demands": [d.get("id") for d in demands]
                })
                
            # Caso B: Diagnóstico Isolado (Regra de Obstrução de Ramal)
            elif count == 1:
                d = demands[0]
                srv = str(d.get("servico", "")).upper()
                
                if "FALTA AGUA" in srv:
                    # Se está isolado espacialmente (len==1), sugere obstrução no ramal
                    events.append({
                        "type": "ISOLATED_DIAGNOSTIC",
                        "severity": "NORMAL",
                        "description": f"Diagnóstico de Obstrução Local para Matrícula {d.get('matricula')}",
                        "impact": "Imóvel isolado",
                        "probable_cause": "Obstrução no ramal do imóvel (Possível vestígio no hidrômetro/ferrolho)",
                        "location": f"{logradouro} ({setor})",
                        "demands": [d.get("id")]
                    })
                    
        return events

async def test():
    clusterer = HydraulicClusterer()
    data = await clusterer.get_recent_data()
    print(f"Dados recuperados: {len(data)}")
    events = clusterer.detect_events(data)
    print(f"Eventos detectados: {len(events)}")
    for e in events[:3]:
        print(f" - [{e['type']}] {e['description']} -> {e['probable_cause']}")

if __name__ == "__main__":
    asyncio.run(test())
