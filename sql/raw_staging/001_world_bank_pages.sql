CREATE SCHEMA IF NOT EXISTS raw_staging;

CREATE TABLE IF NOT EXISTS raw_staging.world_bank_pages (
    run_id          UUID        NOT NULL,
    dataset         TEXT        NOT NULL,
    indicator_id    TEXT        NOT NULL,
    page_number     INTEGER     NOT NULL,
    pages_expected  INTEGER     NOT NULL,
    payload         JSONB       NOT NULL,
    source          TEXT        NOT NULL,
    source_url      TEXT,
    object_key      TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_world_bank_pages PRIMARY KEY (run_id, dataset, page_number),
    CONSTRAINT ck_page_positive    CHECK (page_number >= 1),
    CONSTRAINT ck_page_in_range    CHECK (page_number <= pages_expected)
);

