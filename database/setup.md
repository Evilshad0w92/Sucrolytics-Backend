# Database Setup

## Local (PostgreSQL)

```bash
# 1. Create the database
createdb sucrolytics

# 2. Apply schema
psql sucrolytics < database/schema.sql

# 3. Seed demo data
psql sucrolytics < database/seed.sql

# 4. Copy environment file
cp .env.example .env
# Edit .env with your DATABASE_URL
```

## Demo credentials (password: Sucro2025!)
| Email | Role |
|---|---|
| admin@sucrolytics.com | super_admin |
| lab@sucrolytics.com | lab |
| operador@sucrolytics.com | operator |

## Render (production)
1. Create a PostgreSQL database in Render
2. Copy the connection string to `DATABASE_URL`
3. Run the schema and seed against the Render DB:
   ```bash
   psql $DATABASE_URL < database/schema.sql
   psql $DATABASE_URL < database/seed.sql
   ```
