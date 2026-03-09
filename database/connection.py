"""Módulo de conexão com o Supabase (REST API)."""

import httpx
import pandas as pd
from config.settings import get_settings


class SupabaseClient:
    """Cliente HTTP para a API REST do Supabase."""

    def __init__(self):
        settings = get_settings()
        self.base_url = f"{settings.supabase_url}/rest/v1"
        # Use service key for backend (bypasses RLS)
        key = settings.supabase_service_key or settings.supabase_anon_key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # --- Async methods (for FastAPI routes) ---

    async def get(self, table: str, params: dict | list = None) -> list:
        """GET request para uma tabela/view do Supabase."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url}/{table}",
                headers=self.headers,
                params=params if params is not None else {},
            )
            response.raise_for_status()
            return response.json()

    async def post(self, table: str, data: dict | list) -> list:
        """POST (insert) em uma tabela do Supabase."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/{table}",
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()
            return response.json()

    async def patch(self, table: str, data: dict, params: dict) -> list:
        """PATCH (update) em uma tabela do Supabase."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.patch(
                f"{self.base_url}/{table}",
                headers=self.headers,
                json=data,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def rpc(self, function_name: str, params: dict = None) -> any:
        """Chama uma função RPC do Supabase."""
        settings = get_settings()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.supabase_url}/rest/v1/rpc/{function_name}",
                headers=self.headers,
                json=params or {},
            )
            response.raise_for_status()
            return response.json()

    # --- Sync methods (for ML pipeline) ---

    def get_sync(self, table: str, params: dict = None) -> list:
        """GET síncrono para uso no ML pipeline e em rotas HTTP sem lock de pool."""
        import urllib.request
        import urllib.parse
        import json
        
        query_string = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}/{table}?{query_string}" if params else f"{self.base_url}/{table}"
        
        req = urllib.request.Request(url, headers=self.headers)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status >= 400:
                    raise Exception(f"HTTP Error {response.status}: {response.read()}")
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Erro no urllib request ({table}): {e}")
            return []

    def post_sync(self, table: str, data: dict | list) -> list:
        """POST síncrono para uso no ML pipeline."""
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{self.base_url}/{table}",
                headers=self.headers,
                json=data,
            )
            response.raise_for_status()
            return response.json()

    def fetch_dataframe(self, table: str, params: dict = None) -> pd.DataFrame:
        """Busca dados e retorna como DataFrame (para ML)."""
        data = self.get_sync(table, params)
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)

    def fetch_all_paginated(self, table: str, select: str = "*", order: str = "id", page_size: int = 1000) -> pd.DataFrame:
        """Busca todos os registros de uma tabela com paginação."""
        all_data = []
        offset = 0
        while True:
            params = {
                "select": select,
                "order": order,
                "limit": str(page_size),
                "offset": str(offset),
            }
            batch = self.get_sync(table, params)
            if not batch:
                break
            all_data.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
            print(f"   Coletados {len(all_data)} registros...")

        if not all_data:
            return pd.DataFrame()
        return pd.DataFrame(all_data)


def get_supabase_client() -> SupabaseClient:
    """Factory para o cliente Supabase."""
    return SupabaseClient()


def test_connection() -> bool:
    """Testa a conexão com o Supabase via REST API."""
    try:
        client = SupabaseClient()
        # Tenta buscar 1 registro da tabela solicitacoes
        data = client.get_sync("solicitacoes", {"limit": "1"})
        count = len(data) if isinstance(data, list) else 0
        print(f"✅ Conexão Supabase REST OK (solicitacoes: {count} registros de teste)")
        return True
    except Exception as e:
        print(f"❌ Erro na conexão Supabase: {e}")
        return False
