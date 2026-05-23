-- Sucrolytics — Seed data
-- Run AFTER schema.sql
-- Password for all demo users: Sucro2025!

INSERT INTO organizations(name, slug, timezone)
VALUES ('Ingenio Demo', 'ingenio-demo', 'America/Mexico_City')
ON CONFLICT(slug) DO NOTHING;

-- Super admin (password: Sucro2025!)
-- bcrypt hash generated with passlib
INSERT INTO users(org_id, email, password_hash, name, role)
SELECT id,
       'admin@sucrolytics.com',
       '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGNh6jNpqPpEqz9zHQVGGjJLBxO',  -- Sucro2025!
       'Administrador',
       'super_admin'
FROM organizations WHERE slug='ingenio-demo'
ON CONFLICT(email) DO NOTHING;

INSERT INTO users(org_id, email, password_hash, name, role)
SELECT id,
       'lab@sucrolytics.com',
       '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGNh6jNpqPpEqz9zHQVGGjJLBxO',
       'Quimico Lab',
       'lab'
FROM organizations WHERE slug='ingenio-demo'
ON CONFLICT(email) DO NOTHING;

INSERT INTO users(org_id, email, password_hash, name, role)
SELECT id,
       'operador@sucrolytics.com',
       '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGNh6jNpqPpEqz9zHQVGGjJLBxO',
       'Operador Molienda',
       'operator'
FROM organizations WHERE slug='ingenio-demo'
ON CONFLICT(email) DO NOTHING;

-- Active zafra
INSERT INTO zafras(org_id, name, start_date, is_active)
SELECT id, '2024/2025', '2024-11-01', TRUE
FROM organizations WHERE slug='ingenio-demo'
ON CONFLICT(org_id, name) DO NOTHING;
