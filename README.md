# 💧 SanealA - Plataforma de Inteligência Operacional

![SanealA Logo](https://img.shields.io/badge/SanealA-Intelig%C3%AAncia_Operacional-0052cc?style=for-the-badge&logo=water)
![Python](https://img.shields.io/badge/Python-3.14-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688?style=for-the-badge&logo=fastapi)
![Machine Learning](https://img.shields.io/badge/Machine_Learning-Scikit_Learn-orange?style=for-the-badge&logo=scikit-learn)

**SanealA** é um motor preditivo e de inteligência artificial focado no setor de saneamento básico. O sistema analisa massas de dados de serviços (como falta d'água, vazamentos, reparos de rede) e utiliza modelos de **Machine Learning** e **LLMs (Large Language Models)** para prever a probabilidade de reincidência de falhas estruturais, otimizando a tomada de decisão das equipes de campo e reduzindo o passivo operacional.

---

## 🚀 Arquitetura e Funcionalidades

O SanealA não é apenas um dashboard, é um **cérebro matemático** acoplado a um orquestrador de automação.

### 🧠 1. Pipeline de Machine Learning
O sistema possui um pipeline completo (`ml.pipeline`) que aprende com o histórico de atendimentos (milhares de registros).
- **Extração de Features:** Mapeia matrículas (clientes), logradouros (ruas/bairros), tipos de serviço (ex: ramal predial, rede distribuidora) e recência (tempo desde a última ocorrência).
- **Treinamento e Predição:** Utiliza o algoritmo *RandomForestClassifier* tunado (class_weight='balanced') para identificar padrões sutis que humanos poderiam ignorar. Ele não apenas diz "sim ou não", ele entrega uma **Probabilidade de Recorrência (0 a 100%)**.
- **Agendamento (Retreinamento Contínuo):** O modelo é desenhado para evoluir. Conforme novos dados entram no Supabase, o modelo pode ser retreinado para incorporar novas dinâmicas operacionais da cidade.

### 🤖 2. NLP e Agente de IA (Grok)
- **Análise Semântica:** O módulo `agent.nlp` lê as observações deixadas por clientes e técnicos (texto livre) usando Processamento de Linguagem Natural através do modelo `x-ai/grok-4.1-fast`. Ele identifica se o cliente está `Agressivo`, `Irritado`, `Sem água há dias` e cruza isso com o risco técnico.
- **Relatório Técnico Heurístico:** A integração cruza a predição matemática com a heurística de inteligência (ex: 6 meses vs 24 meses) para gerar insights em linguagem clara, como: *"ALERTA CRÍTICO: Risco de 98% de recorrência. O volume de chamados na matrícula confirma falha crônica."*

### 🔌 3. API e Integração (Servidor Central)
A API construída em **FastAPI** serve como ponte entre a inteligência matemáticaizada e os painéis de consumo (ex: Lovable, Supabase Edge Functions).
- Recebe requisições via `POST /api/integrations/analyze-external-demands`.
- Calcula o score em tempo real baseando-se no modelo `.joblib`.
- Retorna JSONs estruturados para enriquecer painéis gerenciais (Dashboards).

---

## 🛠️ Como Rodar o Projeto

Este repositório contém todo o motor do SanealA.

### 1. Pré-requisitos
- Python 3.10+ (Homologado na v3.14 local).
- Pip (Gerenciador de pacotes do Python).
- Supabase (Para hospedagem do banco de dados).

### 2. Clonando o Repositório
```bash
git clone git@github.com:gleisson-santos/Saneaia.git
cd Saneaia
```

### 3. Configurando o Ambiente
Crie as variáveis de ambiente base. O SanealA requer acesso ao banco (Supabase) e ao motor LLM (OpenRouter).

Crie um arquivo `.env` na raiz do projeto:
```env
# Banco de Dados
SUPABASE_URL=sua_url_aqui
SUPABASE_KEY=sua_chave_anon_aqui
SUPABASE_SERVICE_ROLE_KEY=sua_chave_secreta_aqui # Para o motor de análise profunda

# IA NLP
OPENROUTER_API_KEY=sua_chave_openrouter
```

### 4. Instalando Dependências
Recomenda-se o uso de um ambiente virtual (`.venv`):
```bash
python -m venv .venv
# Ativar no Windows:
.venv\Scripts\activate
# Ativar no Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
```

### 5. Executando o Servidor Local
Para levantar o cérebro SanealA:
```bash
python main.py
```
O servidor estará acessível em `http://localhost:8000`.
- Documentação interativa da API: `http://localhost:8000/docs`.

---

## 📈 Dashboard Gerencial Local

O SanealA conta com um **Dashboard Minimalista Dark Mode** (em `static/index.html`) que consome a própria API localmente. Ele serve como painel de controle direto para:
- Visualizar métricas de predição do modelo de ML (Accuracy, Recall, Precision).
- Analisar a fila de reincidência por região.
- Disparar o pipeline de retreinamento (`Re-treinar Modelo`) com um clique, conectando diretamente com `ml.pipeline`.

**Dica de Fluxo:** Você carrega a base de dados em Excel (planilha bruta) para o Supabase, acessa o Dashboard Local, e pede para a IA estudar os novos dados. Automaticamente, o sistema externo (Lovable) passa a consumir os palpites mais modernos!

---

## 🐳 Deploy para Produção (VPS)

O projeto está pronto para dockerização para rodar em uma VPS (Virtual Private Server).

```bash
docker compose up -d --build
```
*Isto irá construir a imagem encapsulada e iniciar a API de forma persistente. Basta configurar o Nginx na VPS para expor o servidor na web e o sistema funcionará 24/7 sem necessidade de túneis locais.*

---

**SanealA** - *Antecipando a manutenção, evitando a reclamação.* 
