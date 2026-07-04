-- CFO Agent (capivarex-cfo) — tabelas no Cerebro Compartilhado
-- Projeto Supabase: bybocxguyoejfdhlszpo
-- APLICAR SOMENTE APOS APROVACAO DO HENRIQUE.

-- 1) Livro-razao: uma linha por evento Stripe relevante
create table if not exists public.financial_ledger (
  id uuid primary key default gen_random_uuid(),
  stripe_event_id text not null unique,   -- idempotencia garantida pelo banco
  product_slug text,                      -- null => sem metadata no Stripe
  event_type text not null check (event_type in (
    'payment_succeeded', 'refund', 'subscription_created',
    'subscription_cancelled', 'invoice_paid', 'invoice_failed'
  )),
  gross_amount numeric(12, 2) not null,   -- reembolso entra negativo
  currency text,
  company_share numeric(12, 2),           -- null enquanto pending_classification
  pro_labore_share numeric(12, 2),
  split_rule_applied text,                -- ex.: 'curso-x:70/30'; null se sem regra
  status text not null check (status in (
    'classified', 'pending_classification', 'error'
  )),
  raw_stripe_payload jsonb not null,      -- evento bruto, para auditoria
  created_at timestamptz not null default now()
);

create index if not exists idx_financial_ledger_product_slug
  on public.financial_ledger (product_slug);
create index if not exists idx_financial_ledger_status
  on public.financial_ledger (status);
create index if not exists idx_financial_ledger_created_at
  on public.financial_ledger (created_at);

-- 2) Regras de split aprovadas por humano (nunca criadas automaticamente)
create table if not exists public.product_split_rules (
  id uuid primary key default gen_random_uuid(),
  product_slug text not null unique,
  company_pct numeric(5, 2) not null check (company_pct between 0 and 100),
  pro_labore_pct numeric(5, 2) not null check (pro_labore_pct between 0 and 100),
  approved_by text not null default 'Henrique',
  rationale text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  constraint split_must_sum_100 check (company_pct + pro_labore_pct = 100)
);

-- 3) Seguranca: RLS ligado, nenhuma policy criada de proposito.
-- So a service_role key (backend) acessa; a anon key nao enxerga nada.
alter table public.financial_ledger enable row level security;
alter table public.product_split_rules enable row level security;
