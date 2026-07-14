-- Multi-tenancy (Fase 1) — indices de account_id
-- As colunas account_id JA EXISTEM (criadas fora deste repo); aqui so os
-- indices, porque TODA leitura agora filtra por account_id.
-- APLICAR SOMENTE APOS APROVACAO DO HENRIQUE.

create index if not exists idx_financial_ledger_account_id
  on public.financial_ledger (account_id);

create index if not exists idx_spending_requests_account_id
  on public.spending_requests (account_id);

create index if not exists idx_spending_approvals_account_id
  on public.spending_approvals (account_id);
