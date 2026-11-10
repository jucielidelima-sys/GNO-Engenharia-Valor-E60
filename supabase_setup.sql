-- Execute uma única vez no SQL Editor do projeto engenharia-valor-e60.
-- Não altera as quatro tabelas já criadas.
CREATE TABLE IF NOT EXISTS public.e60_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    saved_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL
);
ALTER TABLE public.e60_snapshots ENABLE ROW LEVEL SECURITY;
-- Sem políticas públicas: somente o backend com chave secreta (service_role)
-- acessa os dados. NUNCA exponha essa chave no GitHub ou no navegador.
CREATE INDEX IF NOT EXISTS e60_snapshots_id_desc_idx ON public.e60_snapshots (id DESC);
