from fastapi import APIRouter, Query
from typing import Optional
from api.ml.clustering import HydraulicClusterer

router = APIRouter(prefix="/api/ml", tags=["Inteligência Operacional (ML)"])

@router.get("/events")
async def get_ml_events(
    hours: int = Query(default=48, ge=1, le=168),
):
    """Retorna eventos detectados pelo motor de clustering (Eventos Mestres e Diagnósticos)."""
    clusterer = HydraulicClusterer()
    data = await clusterer.get_recent_data(hours=hours)
    events = clusterer.detect_events(data)
    
    return {
        "count": len(events),
        "events": events
    }
