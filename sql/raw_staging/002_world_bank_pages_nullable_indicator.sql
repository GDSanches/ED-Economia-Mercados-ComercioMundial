-- Datasets de referência (ex.: countries, o cadastro de entidades) não têm indicador.
-- Pode ser executado várias vezes: remover um NOT NULL que já não existe não gera erro.
ALTER TABLE raw_staging.world_bank_pages ALTER COLUMN indicator_id DROP NOT NULL;
