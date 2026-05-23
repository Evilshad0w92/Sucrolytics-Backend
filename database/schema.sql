-- Sucrolytics Database Schema
-- PostgreSQL 14+

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── ORGANIZATIONS (multi-tenant) ────────────────────────────────────────────
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    slug        VARCHAR(100) UNIQUE NOT NULL,
    timezone    VARCHAR(50)  DEFAULT 'America/Mexico_City',
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── USERS ────────────────────────────────────────────────────────────────────
-- Roles: super_admin > admin > supervisor > operator | lab | readonly
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    username      VARCHAR(100) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(200) NOT NULL,
    role          VARCHAR(20)  NOT NULL CHECK (role IN ('super_admin','admin','supervisor','operator','lab','readonly')),
    is_active     BOOLEAN      DEFAULT TRUE,
    created_at    TIMESTAMPTZ  DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX idx_users_org ON users(org_id);

-- ─── ZAFRAS (harvest seasons) ─────────────────────────────────────────────────
CREATE TABLE zafras (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,   -- e.g. "2021/2022"
    start_date  DATE         NOT NULL,
    end_date    DATE,
    is_active   BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE(org_id, name)
);
CREATE INDEX idx_zafras_org ON zafras(org_id);

-- ─── DAILY MOLIENDA (entered by operator) ─────────────────────────────────────
CREATE TABLE daily_molienda (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                UUID        NOT NULL REFERENCES organizations(id),
    zafra_id              UUID        NOT NULL REFERENCES zafras(id),
    date                  DATE        NOT NULL,
    cana_recibida_tons    NUMERIC(12,3),
    cana_molida_bruta_tons NUMERIC(12,3),
    agua_imbibicion_tons  NUMERIC(12,3),
    dias_zafra            INTEGER,
    horas_zafra           NUMERIC(8,3),
    horas_molienda        NUMERIC(8,3),
    horas_perdidas        NUMERIC(8,3),
    entered_by            UUID        REFERENCES users(id),
    entered_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_by            UUID        REFERENCES users(id),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);
CREATE INDEX idx_molienda_date ON daily_molienda(org_id, zafra_id, date);

-- ─── LAB: CAÑA ────────────────────────────────────────────────────────────────
CREATE TABLE daily_lab_cana (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        NOT NULL REFERENCES organizations(id),
    zafra_id    UUID        NOT NULL REFERENCES zafras(id),
    date        DATE        NOT NULL,
    fibra_pct   NUMERIC(8,4),
    entered_by  UUID        REFERENCES users(id),
    entered_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_by  UUID        REFERENCES users(id),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: JUGO MEZCLADO ───────────────────────────────────────────────────────
CREATE TABLE daily_lab_jugo_mezclado (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID        NOT NULL REFERENCES organizations(id),
    zafra_id     UUID        NOT NULL REFERENCES zafras(id),
    date         DATE        NOT NULL,
    tons         NUMERIC(12,3),
    brix         NUMERIC(8,4),
    sacarosa_pct NUMERIC(8,4),
    ph           NUMERIC(6,3),
    -- pureza = sacarosa/brix*100 (calculated by API)
    entered_by   UUID        REFERENCES users(id),
    entered_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_by   UUID        REFERENCES users(id),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: JUGO RESIDUAL ───────────────────────────────────────────────────────
CREATE TABLE daily_lab_jugo_residual (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID        NOT NULL REFERENCES organizations(id),
    zafra_id     UUID        NOT NULL REFERENCES zafras(id),
    date         DATE        NOT NULL,
    brix         NUMERIC(8,4),
    sacarosa_pct NUMERIC(8,4),
    -- pureza calculated
    entered_by   UUID        REFERENCES users(id),
    entered_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_by   UUID        REFERENCES users(id),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: JUGO CLARO ──────────────────────────────────────────────────────────
CREATE TABLE daily_lab_jugo_claro (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID        NOT NULL REFERENCES organizations(id),
    zafra_id   UUID        NOT NULL REFERENCES zafras(id),
    date       DATE        NOT NULL,
    pureza     NUMERIC(8,4),
    entered_by UUID        REFERENCES users(id),
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by UUID        REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: BAGAZO ──────────────────────────────────────────────────────────────
-- brix_bagazo = sacarosa_pct / pureza_jugo_residual * 100  (calculated)
-- fibra_pct_bagazo = 100 - brix_bagazo - humedad_pct         (calculated)
-- tons_bagazo = tons_cana_molida * fibra_pct_cana / fibra_pct_bagazo (calculated)
CREATE TABLE daily_lab_bagazo (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID        NOT NULL REFERENCES organizations(id),
    zafra_id      UUID        NOT NULL REFERENCES zafras(id),
    date          DATE        NOT NULL,
    sacarosa_pct  NUMERIC(8,4),
    humedad_pct   NUMERIC(8,4),
    entered_by    UUID        REFERENCES users(id),
    entered_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_by    UUID        REFERENCES users(id),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: CACHAZA ─────────────────────────────────────────────────────────────
-- tons_cachaza = cachaza_pct_cana * tons_cana_molida / 100 (calculated)
CREATE TABLE daily_lab_cachaza (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID        NOT NULL REFERENCES organizations(id),
    zafra_id         UUID        NOT NULL REFERENCES zafras(id),
    date             DATE        NOT NULL,
    cachaza_pct_cana NUMERIC(8,4),   -- % cachaza/caña (user input)
    sacarosa_pct     NUMERIC(8,4),
    brix             NUMERIC(8,4),
    entered_by       UUID        REFERENCES users(id),
    entered_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_by       UUID        REFERENCES users(id),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── LAB: MIEL FINAL ──────────────────────────────────────────────────────────
CREATE TABLE daily_lab_miel_final (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                     UUID        NOT NULL REFERENCES organizations(id),
    zafra_id                   UUID        NOT NULL REFERENCES zafras(id),
    date                       DATE        NOT NULL,
    tons_fisica                NUMERIC(12,3),  -- medición física (user input)
    tons_total                 NUMERIC(12,3),  -- total incluyendo ajuste
    sacarosa_a_miel_final_tons NUMERIC(12,3),  -- tons sacarosa a miel final (user input)
    sacarosa_recuperable_tons  NUMERIC(12,3),  -- tons sacarosa recuperable (user input)
    brix                       NUMERIC(8,4),
    sacarosa_pct               NUMERIC(8,4),
    pureza_fecha               NUMERIC(8,4),   -- pureza acumulada a la fecha
    entered_by                 UUID        REFERENCES users(id),
    entered_at                 TIMESTAMPTZ DEFAULT NOW(),
    updated_by                 UUID        REFERENCES users(id),
    updated_at                 TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── PRODUCCION: AZÚCAR (por tipo de producto) ────────────────────────────────
CREATE TABLE daily_produccion_azucar (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                  UUID        NOT NULL REFERENCES organizations(id),
    zafra_id                UUID        NOT NULL REFERENCES zafras(id),
    date                    DATE        NOT NULL,
    -- Refinado
    refinado_tons           NUMERIC(12,3),
    refinado_pol_pct        NUMERIC(8,4),
    refinado_pureza         NUMERIC(8,4),
    -- Estándar
    estandar_tons           NUMERIC(12,3),
    estandar_pol_pct        NUMERIC(8,4),
    estandar_pureza         NUMERIC(8,4),
    -- Crudo
    crudo_tons              NUMERIC(12,3),
    crudo_pol_pct           NUMERIC(8,4),
    crudo_pureza            NUMERIC(8,4),
    -- Stock acumulado P y E (fin del día)
    stock_azucar_pye_tons   NUMERIC(12,3),
    stock_miel_final_tons   NUMERIC(12,3),
    entered_by              UUID        REFERENCES users(id),
    entered_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_by              UUID        REFERENCES users(id),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);

-- ─── BALANCE DE POL (calculado y almacenado) ──────────────────────────────────
-- Columns N/O/P/Q/R/S/T/U from spreadsheet = total/refinado/estandar/crudo
CREATE TABLE daily_pol_balance (
    id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                    UUID        NOT NULL REFERENCES organizations(id),
    zafra_id                  UUID        NOT NULL REFERENCES zafras(id),
    date                      DATE        NOT NULL,
    -- Intermedios calculados
    tons_bagazo               NUMERIC(12,3),
    brix_bagazo               NUMERIC(8,4),
    fibra_pct_bagazo          NUMERIC(8,4),
    pureza_jugo_residual      NUMERIC(8,4),
    sacarosa_pct_cana         NUMERIC(8,4),
    pol_jugo_mezclado_dia     NUMERIC(12,4),
    -- Pérdidas DIA (tons)
    perdida_bagazo_dia        NUMERIC(12,4),
    perdida_miel_final_dia    NUMERIC(12,4),
    perdida_cachaza_dia       NUMERIC(12,4),
    perdida_indeterminada_dia NUMERIC(12,4),
    perdidas_totales_dia      NUMERIC(12,4),
    pol_azucar_pye_dia        NUMERIC(12,4),
    pol_en_cana_dia           NUMERIC(12,4),
    -- Pérdidas DIA (% caña)
    perdida_bagazo_pct        NUMERIC(8,4),
    perdida_miel_final_pct    NUMERIC(8,4),
    perdida_cachaza_pct       NUMERIC(8,4),
    perdida_indeterminada_pct NUMERIC(8,4),
    perdidas_totales_pct      NUMERIC(8,4),
    pol_azucar_pye_pct        NUMERIC(8,4),
    pol_en_cana_pct           NUMERIC(8,4),
    -- Pérdidas FECHA (acumulado a la fecha, tons)
    perdida_bagazo_fecha        NUMERIC(12,4),
    perdida_miel_final_fecha    NUMERIC(12,4),
    perdida_cachaza_fecha       NUMERIC(12,4),
    perdida_indeterminada_fecha NUMERIC(12,4),
    perdidas_totales_fecha      NUMERIC(12,4),
    pol_azucar_pye_fecha        NUMERIC(12,4),
    pol_en_cana_fecha           NUMERIC(12,4),
    -- Por producto (refinado/estandar/crudo)
    refinado_perdida_bagazo_dia     NUMERIC(12,4),
    refinado_perdida_miel_final_dia NUMERIC(12,4),
    refinado_perdida_cachaza_dia    NUMERIC(12,4),
    refinado_perdida_indet_dia      NUMERIC(12,4),
    refinado_perdidas_totales_dia   NUMERIC(12,4),
    refinado_pol_azucar_dia         NUMERIC(12,4),
    refinado_pol_cana_dia           NUMERIC(12,4),
    estandar_perdida_bagazo_dia     NUMERIC(12,4),
    estandar_perdida_miel_final_dia NUMERIC(12,4),
    estandar_perdida_cachaza_dia    NUMERIC(12,4),
    estandar_perdida_indet_dia      NUMERIC(12,4),
    estandar_perdidas_totales_dia   NUMERIC(12,4),
    estandar_pol_azucar_dia         NUMERIC(12,4),
    estandar_pol_cana_dia           NUMERIC(12,4),
    crudo_perdida_bagazo_dia        NUMERIC(12,4),
    crudo_perdida_miel_final_dia    NUMERIC(12,4),
    crudo_perdida_cachaza_dia       NUMERIC(12,4),
    crudo_perdida_indet_dia         NUMERIC(12,4),
    crudo_perdidas_totales_dia      NUMERIC(12,4),
    crudo_pol_azucar_dia            NUMERIC(12,4),
    crudo_pol_cana_dia              NUMERIC(12,4),
    calculated_at             TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, zafra_id, date)
);
CREATE INDEX idx_balance_date ON daily_pol_balance(org_id, zafra_id, date);

-- ─── IMPORTACIONES DE DATOS HISTÓRICOS ────────────────────────────────────────
CREATE TABLE data_imports (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID         NOT NULL REFERENCES organizations(id),
    zafra_id      UUID         REFERENCES zafras(id),
    filename      VARCHAR(255),
    status        VARCHAR(20)  CHECK (status IN ('pending','processing','completed','failed')),
    total_rows    INTEGER      DEFAULT 0,
    imported_rows INTEGER      DEFAULT 0,
    error_count   INTEGER      DEFAULT 0,
    errors        JSONB,
    imported_by   UUID         REFERENCES users(id),
    imported_at   TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── ALERTAS ──────────────────────────────────────────────────────────────────
CREATE TABLE alert_thresholds (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID         NOT NULL REFERENCES organizations(id),
    metric_name  VARCHAR(100) NOT NULL,
    min_value    NUMERIC(12,4),
    max_value    NUMERIC(12,4),
    alert_emails TEXT[]       DEFAULT '{}',
    is_active    BOOLEAN      DEFAULT TRUE,
    created_at   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE alert_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID         NOT NULL REFERENCES organizations(id),
    threshold_id  UUID         REFERENCES alert_thresholds(id),
    date          DATE         NOT NULL,
    metric_name   VARCHAR(100) NOT NULL,
    actual_value  NUMERIC(12,4),
    triggered_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ─── UPDATED_AT TRIGGER ───────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'organizations','users','daily_molienda','daily_lab_cana',
    'daily_lab_jugo_mezclado','daily_lab_jugo_residual','daily_lab_jugo_claro',
    'daily_lab_bagazo','daily_lab_cachaza','daily_lab_miel_final',
    'daily_produccion_azucar'
  ] LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %s
       FOR EACH ROW EXECUTE FUNCTION update_updated_at()', t, t
    );
  END LOOP;
END $$;
