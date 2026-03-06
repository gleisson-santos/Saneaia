"""Script de importacao de dados Excel para Supabase via REST API."""

import pandas as pd
import json
import math
from database.connection import get_supabase_client


# Mapeamento de colunas Excel -> SQL
COLUMN_MAP = {
    "SS": "ss",
    "OS": "os_numero",
    "Tipo": "tipo",
    "Especificação": "especificacao",
    "Serviço": "servico",
    "Unid Atual (OS)": "unidade_os",
    "Matrícula": "matricula",
    "Logradouro": "logradouro",
    "CEP": "cep",
    "Encerramento": "data_encerramento",
    "Obs da SS": "observacao",
    "Sit da OS": "situacao",
    "Data/Hora Última Tramitação da OS": "data_ultima_tramitacao",
    "Localidade": "localidade",
    "Nome do Mês": "mes",
    "Setor": "setor",
    "Bairro": "bairro",
}


def import_excel(file_path: str, batch_size: int = 2000, clear_table: bool = False):
    """Importa dados de um arquivo Excel para Supabase via REST API."""

    print(f"Lendo arquivo: {file_path}")
    df = pd.read_excel(file_path)
    print(f"   {df.shape[0]} linhas x {df.shape[1]} colunas")
    print(f"   Colunas: {list(df.columns)}")

    # Renomear colunas
    df = df.rename(columns=COLUMN_MAP)

    # Converter tipos string
    for col in ["ss", "matricula", "os_numero"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # CEP: tratar float -> string
    if "cep" in df.columns:
        df["cep"] = df["cep"].apply(
            lambda x: str(int(x)) if pd.notna(x) and not (isinstance(x, float) and math.isnan(x)) else None
        )

    # Logradouro: normalizar
    if "logradouro" in df.columns:
        df["logradouro"] = df["logradouro"].astype(str).str.strip().str.upper()
        df["logradouro"] = df["logradouro"].replace({"NAN": None, "NONE": None, "": None})

    # Servico: normalizar
    if "servico" in df.columns:
        df["servico"] = df["servico"].astype(str).str.strip()
        df["servico"] = df["servico"].replace({"nan": None, "None": None})

    # Datas -> ISO string
    for col in ["data_encerramento", "data_ultima_tramitacao"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].apply(
                lambda x: x.isoformat() if pd.notna(x) else None
            )

    # Selecionar apenas colunas mapeadas
    valid_cols = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[valid_cols]

    # Limpar NaN -> None
    df = df.where(pd.notna(df), None)

    supabase = get_supabase_client()

    # Limpar tabela se solicitado
    if clear_table:
        print("Limpando tabela solicitacoes...")
        try:
            import httpx
            with httpx.Client(timeout=30) as client:
                r = client.delete(
                    f"{supabase.base_url}/solicitacoes",
                    headers={**supabase.headers, "Prefer": "return=minimal"},
                    params={"id": "not.is.null"},
                )
                print(f"   Limpeza: {r.status_code}")
        except Exception as e:
            print(f"   Erro na limpeza: {e}")

    print(f"Inserindo {len(df)} registros...")

    total_inserted = 0
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i + batch_size]
        records = batch.to_dict(orient="records")

        # Limpar None/NaN para JSON
        clean_records = []
        for record in records:
            clean = {}
            for k, v in record.items():
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    clean[k] = None
                else:
                    clean[k] = v
            clean_records.append(clean)

        try:
            supabase.post_sync("solicitacoes", clean_records)
            total_inserted += len(clean_records)
            if total_inserted % 2000 == 0 or total_inserted == len(df):
                print(f"   {total_inserted}/{len(df)} registros inseridos")
        except Exception as e:
            print(f"   Erro no lote {i}-{i + batch_size}: {e}")

    print(f"Importacao concluida: {total_inserted} registros.")
    return total_inserted


if __name__ == "__main__":
    import sys

    file_path = sys.argv[1] if len(sys.argv) > 1 else "desenvolvimento/dados_base/Dados.xlsx"
    clear = "--clear" in sys.argv

    import_excel(file_path, clear_table=clear)
