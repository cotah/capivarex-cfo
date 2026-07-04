# Capivarex CFO Agent

Backend financeiro da Capivarex AI Company. Escuta a conta Stripe **Factory**
(somente leitura de eventos), registra cada venda/reembolso/assinatura num
livro-razao (`financial_ledger`) e aplica a regra de split **previamente
aprovada por humano** (`product_split_rules`).

## Regras de arquitetura (nao-negociaveis)

- **Nunca move dinheiro.** O projeto nao tem SDK do Stripe nem secret key da
  API — so o webhook signing secret, que serve apenas para validar assinatura.
- **Nunca decide split sozinho.** Produto sem regra aprovada vira
  `pending_classification` (shares nulos), destacado no relatorio.
  Nunca aplicamos porcentagem default.
- **Falhar visivel > numero errado silencioso.**

## Endpoints

| Metodo | Rota | Auth |
|---|---|---|
| POST | `/webhooks/stripe` | Assinatura Stripe (`STRIPE_WEBHOOK_SECRET`) |
| POST | `/split-rules` | Header `X-API-Key` (`CFO_API_KEY`) |
| GET | `/reports/summary?product_slug=&since=` | Header `X-API-Key` |
| GET | `/health` | nenhuma |

## Rodar localmente

```bash
# 1. Criar venv e instalar dependencias (Windows)
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt

# 2. Rodar os testes (nao precisam de .env nem de internet)
.venv\Scripts\python -m pytest

# 3. Subir o servidor (precisa do .env preenchido — veja .env.example)
copy .env.example .env   # e preencha os valores reais
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Banco

Tabelas no Supabase "Cerebro Compartilhado" (`bybocxguyoejfdhlszpo`).
SQL em `migrations/001_create_cfo_tables.sql`. RLS ligado sem policies:
so o backend (service_role) acessa.

## Deploy (Railway)

`Procfile` + `requirements.txt` + `.python-version` ja prontos.
Configure as 4 env vars do `.env.example` no painel do Railway.
