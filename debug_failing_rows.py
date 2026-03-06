import pandas as pd
import math
import httpx
from database.connection import get_supabase_client

df = pd.read_excel("desenvolvimento/dados_base/Dados.xlsx")

col_map = {
    "SS": "ss", "OS": "os_numero", "Tipo": "tipo",
    "Especificação": "especificacao", "Serviço": "servico",
    "Unid Atual (OS)": "unidade_os", "Matrícula": "matricula",
    "Setor": "setor", "Bairro": "bairro", "Logradouro": "logradouro",
    "CEP": "cep", "Encerramento": "data_encerramento",
    "Obs da SS": "observacao", "Localidade": "localidade",
    "Nome do Mês": "mes", "Sit da OS": "situacao",
    "Data/Hora Última Tramitação da OS": "data_ultima_tramitacao",
}

df = df.rename(columns=col_map)
valid = [c for c in col_map.values() if c in df.columns]
df = df[valid]

for col in ["ss", "matricula", "os_numero"]:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip()
if "cep" in df.columns:
    df["cep"] = df["cep"].apply(lambda x: str(int(x)) if pd.notna(x) and not (isinstance(x, float) and math.isnan(x)) else None)
if "logradouro" in df.columns:
    df["logradouro"] = df["logradouro"].astype(str).str.strip().str.upper()
if "servico" in df.columns:
    df["servico"] = df["servico"].astype(str).str.strip()
for col in ["data_encerramento", "data_ultima_tramitacao"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        df[col] = df[col].apply(lambda x: x.isoformat() if pd.notna(x) else None)

df = df.where(pd.notna(df), None)

supabase = get_supabase_client()
client = httpx.Client(timeout=30)

print("Procurando registro com erro entre 2600 e 3000...")
# Test first 1000 records one by one until we find an error
for i in range(2600, 3000):
    record = df.iloc[i].to_dict()
    clean = {k: (v if not (isinstance(v, float) and math.isnan(v)) else None) for k, v in record.items()}
    
    resp = client.post(
        f"{supabase.base_url}/solicitacoes",
        headers={**supabase.headers, "Prefer": "return=minimal"},
        json=[clean],
    )
    if resp.status_code >= 400:
        print(f"Erro no registro {i}:")
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
        print(f"Record: {clean}")
        break
else:
    print("Nenhum erro nos primeiros 1000 registros.")

client.close()
