import asyncio
from database.connection import get_supabase_client

async def main():
    s = get_supabase_client()
    try:
        # Check the analyze view
        res = await s.get("solicitacoes_analise", {"limit": "5"})
        for i, row in enumerate(res):
            print(f"Row {i}: ano={row.get('ano')}, mes={row.get('mes')}, bairro={row.get('bairro')}")
        
    except Exception as e:
        print("Error:", e)

asyncio.run(main())
