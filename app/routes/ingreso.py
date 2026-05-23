"""
ingreso.py — Ingreso diario de datos del balance de POL
Acceso: todos los roles autenticados (el frontend filtra por rol qué formularios ve)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from datetime import date
from typing import Optional
from app.database import get_db
from app.auth.dependencies import get_current_user

router = APIRouter()

# ─── Modelos ──────────────────────────────────────────────────────────────────

class IngresoInicial(BaseModel):
    """Valores de la columna I del Excel (FECHA del día anterior al inicio de zafra)."""
    fecha:    date    # primer día real de datos; se guarda registro daily para fecha-1
    zafra_id: str
    # Sacarosa Aparente FECHA acumulada del período anterior (columna I)
    jm_sac_fecha:      Optional[float] = None  # I53  — JM SAC Aparente FECHA anterior
    miel_sac_fecha:    Optional[float] = None  # I218 — Miel Final SAC Aparente FECHA anterior
    cachaza_sac_fecha: Optional[float] = None  # I94  — Cachaza SAC Aparente FECHA anterior
    azucar_sac_fecha:  Optional[float] = None  # I290 — Azúcar Total SAC Aparente FECHA anterior
    bagazo_sac_fecha:  Optional[float] = None  # I77  — Bagazo SAC Aparente FECHA anterior
    # TONS físicas acumuladas del período anterior (para calcular F70 BAGAZO FECHA)
    cana_fecha_anterior:    Optional[float] = None  # I14 — Caña Molida Bruta TONS FECHA
    agua_fecha_anterior:    Optional[float] = None  # I86 — Agua Imbibición TONS FECHA
    jm_tons_fecha_anterior: Optional[float] = None  # I40 — JM TONS FECHA
    # Stocks del período anterior
    tons_fisica_anterior:          Optional[float] = None  # I375 — stock SAC a miel final
    sacarosa_recuperable_anterior: Optional[float] = None  # I373 — stock SAC recuperable


class IngresoBalanceDia(BaseModel):
    fecha:    date
    zafra_id: str
    # ZAFRA / MOLIENDA
    cana_recibida_dia_ton:        Optional[float] = None
    # AGUA DE IMBIBICION
    agua_imbibicion_dia_ton:      Optional[float] = None
    # JUGO MEZCLADO
    jugo_mezclado_dia_tons:       Optional[float] = None
    # ANALISIS
    jugo_mezclado_sacarosa:       Optional[float] = None
    bagazo_sacarosa_pct:          Optional[float] = None
    miel_final_sacarosa:          Optional[float] = None
    filtro_banda_pol:             Optional[float] = None  # → cachaza.sacarosa_pct
    # PROCESO — MIEL FINAL
    miel_final_fisica_tons:       Optional[float] = None
    sacarosa_a_miel_final_tons:   Optional[float] = None
    sacarosa_recuperable_tons:    Optional[float] = None
    # CACHAZA
    cachaza_dia_tons:             Optional[float] = None
    cachaza_pct_cana:             Optional[float] = None
    # MOLIENDA — caña molida bruta (para cálculo de bagazo)
    cana_molida_bruta_dia_ton:    Optional[float] = None
    # LAB CAÑA
    fibra_pct_cana:               Optional[float] = None
    # LAB BAGAZO — humedad
    humedad_pct_bagazo:           Optional[float] = None
    # JUGO RESIDUAL — para pureza (brix_bagazo)
    jugo_residual_brix:           Optional[float] = None
    jugo_residual_sacarosa_pct:   Optional[float] = None
    # PRODUCCION — AZUCAR
    refinado_tons:                Optional[float] = None
    refinado_pol_pct:             Optional[float] = None
    estandar_tons:                Optional[float] = None
    estandar_pol_pct:             Optional[float] = None
    crudo_tons:                   Optional[float] = None
    crudo_pol_pct:                Optional[float] = None

# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/inicial")
def guardar_inicial(body: IngresoInicial, user=Depends(get_current_user)):
    """Guarda los valores I (FECHA anterior) de la carga inicial de zafra."""
    from datetime import timedelta
    oid     = user["org_id"]
    uid     = user["sub"]
    fecha_0 = body.fecha - timedelta(days=1)   # día previo al primer dato

    with get_db() as conn:
        cur = conn.cursor()

        # Tabla de carga inicial (se crea si no existe)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zafra_inicial (
                org_id              UUID    NOT NULL,
                zafra_id            TEXT    NOT NULL,
                jm_sac_fecha        NUMERIC(12,4),
                miel_sac_fecha      NUMERIC(12,4),
                cachaza_sac_fecha   NUMERIC(12,4),
                azucar_sac_fecha    NUMERIC(12,4),
                bagazo_sac_fecha    NUMERIC(12,4),
                cana_fecha_anterior    NUMERIC(12,3),
                agua_fecha_anterior    NUMERIC(12,3),
                jm_tons_fecha_anterior NUMERIC(12,3),
                tons_fisica_anterior          NUMERIC(12,3),
                sacarosa_recuperable_anterior NUMERIC(12,3),
                entered_by UUID,
                updated_by UUID,
                PRIMARY KEY (org_id, zafra_id)
            )
        """)
        for col, typ in [
            ("cana_fecha_anterior",    "NUMERIC(12,3)"),
            ("agua_fecha_anterior",    "NUMERIC(12,3)"),
            ("jm_tons_fecha_anterior", "NUMERIC(12,3)"),
        ]:
            cur.execute(f"ALTER TABLE zafra_inicial ADD COLUMN IF NOT EXISTS {col} {typ}")

        # Upsert en zafra_inicial
        cur.execute("""
            INSERT INTO zafra_inicial
                (org_id, zafra_id,
                 jm_sac_fecha, miel_sac_fecha, cachaza_sac_fecha,
                 azucar_sac_fecha, bagazo_sac_fecha,
                 cana_fecha_anterior, agua_fecha_anterior, jm_tons_fecha_anterior,
                 tons_fisica_anterior, sacarosa_recuperable_anterior,
                 entered_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id) DO UPDATE SET
                jm_sac_fecha                  = EXCLUDED.jm_sac_fecha,
                miel_sac_fecha                = EXCLUDED.miel_sac_fecha,
                cachaza_sac_fecha             = EXCLUDED.cachaza_sac_fecha,
                azucar_sac_fecha              = EXCLUDED.azucar_sac_fecha,
                bagazo_sac_fecha              = EXCLUDED.bagazo_sac_fecha,
                cana_fecha_anterior           = EXCLUDED.cana_fecha_anterior,
                agua_fecha_anterior           = EXCLUDED.agua_fecha_anterior,
                jm_tons_fecha_anterior        = EXCLUDED.jm_tons_fecha_anterior,
                tons_fisica_anterior          = EXCLUDED.tons_fisica_anterior,
                sacarosa_recuperable_anterior = EXCLUDED.sacarosa_recuperable_anterior,
                updated_by                    = %s
        """, (oid, body.zafra_id,
              body.jm_sac_fecha, body.miel_sac_fecha, body.cachaza_sac_fecha,
              body.azucar_sac_fecha, body.bagazo_sac_fecha,
              body.cana_fecha_anterior, body.agua_fecha_anterior, body.jm_tons_fecha_anterior,
              body.tons_fisica_anterior, body.sacarosa_recuperable_anterior,
              uid, uid))

        # También guarda los stocks en daily_lab_miel_final para fecha-1
        # (permite que la query DIA del cordia.py encuentre I375 e I373)
        cur.execute("""
            INSERT INTO daily_lab_miel_final
                (org_id, zafra_id, date, tons_fisica, sacarosa_recuperable_tons, entered_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                tons_fisica               = EXCLUDED.tons_fisica,
                sacarosa_recuperable_tons = EXCLUDED.sacarosa_recuperable_tons,
                updated_by                = %s
        """, (oid, body.zafra_id, fecha_0,
              body.tons_fisica_anterior, body.sacarosa_recuperable_anterior,
              uid, uid))

    return {"ok": True, "fecha_guardada": str(fecha_0)}


@router.get("/inicial")
def obtener_inicial(zafra_id: str, user=Depends(get_current_user)):
    """Devuelve la carga inicial de la zafra desde zafra_inicial."""
    oid = user["org_id"]
    with get_db() as conn:
        cur = conn.cursor()
        try:
            for col, typ in [
                ("cana_fecha_anterior",    "NUMERIC(12,3)"),
                ("agua_fecha_anterior",    "NUMERIC(12,3)"),
                ("jm_tons_fecha_anterior", "NUMERIC(12,3)"),
            ]:
                cur.execute(f"ALTER TABLE zafra_inicial ADD COLUMN IF NOT EXISTS {col} {typ}")
            cur.execute("""
                SELECT jm_sac_fecha, miel_sac_fecha, cachaza_sac_fecha,
                       azucar_sac_fecha, bagazo_sac_fecha,
                       cana_fecha_anterior, agua_fecha_anterior, jm_tons_fecha_anterior,
                       tons_fisica_anterior, sacarosa_recuperable_anterior
                FROM zafra_inicial
                WHERE org_id=%s AND zafra_id=%s
            """, (oid, zafra_id))
            r = cur.fetchone()
            return dict(r) if r else {}
        except Exception:
            return {}


@router.get("/zafras")
def listar_zafras(user=Depends(get_current_user)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, start_date, end_date, is_active FROM zafras "
            "WHERE org_id = %s ORDER BY start_date DESC",
            (user["org_id"],),
        )
        return cur.fetchall()


@router.get("/dia")
def obtener_dia(fecha: date, zafra_id: str, user=Depends(get_current_user)):
    oid = user["org_id"]
    with get_db() as conn:
        cur = conn.cursor()
        def q(tabla):
            cur.execute(
                f"SELECT * FROM {tabla} WHERE org_id=%s AND zafra_id=%s AND date=%s",
                (oid, zafra_id, fecha),
            )
            r = cur.fetchone()
            return dict(r) if r else None

        return {
            "molienda":      q("daily_molienda"),
            "jugo_mezclado": q("daily_lab_jugo_mezclado"),
            "cana":          q("daily_lab_cana"),
            "bagazo":        q("daily_lab_bagazo"),
            "jugo_residual": q("daily_lab_jugo_residual"),
            "miel_final":    q("daily_lab_miel_final"),
            "cachaza":       q("daily_lab_cachaza"),
            "produccion":    q("daily_produccion_azucar"),
        }


@router.post("/dia")
def guardar_dia(body: IngresoBalanceDia, user=Depends(get_current_user)):
    oid = user["org_id"]
    uid = user["sub"]
    z   = body.zafra_id
    f   = body.fecha

    with get_db() as conn:
        cur = conn.cursor()

        # MOLIENDA
        cur.execute("""
            INSERT INTO daily_molienda
                (org_id, zafra_id, date, cana_recibida_tons, cana_molida_bruta_tons, agua_imbibicion_tons, entered_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                cana_recibida_tons     = EXCLUDED.cana_recibida_tons,
                cana_molida_bruta_tons = EXCLUDED.cana_molida_bruta_tons,
                agua_imbibicion_tons   = EXCLUDED.agua_imbibicion_tons,
                updated_by             = %s
        """, (oid, z, f, body.cana_recibida_dia_ton, body.cana_molida_bruta_dia_ton, body.agua_imbibicion_dia_ton, uid, uid))

        # JUGO MEZCLADO
        cur.execute("""
            INSERT INTO daily_lab_jugo_mezclado
                (org_id, zafra_id, date, tons, sacarosa_pct, entered_by)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                tons         = EXCLUDED.tons,
                sacarosa_pct = EXCLUDED.sacarosa_pct,
                updated_by   = %s
        """, (oid, z, f, body.jugo_mezclado_dia_tons, body.jugo_mezclado_sacarosa, uid, uid))

        # BAGAZO
        cur.execute("""
            INSERT INTO daily_lab_bagazo
                (org_id, zafra_id, date, sacarosa_pct, humedad_pct, entered_by)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                sacarosa_pct = EXCLUDED.sacarosa_pct,
                humedad_pct  = EXCLUDED.humedad_pct,
                updated_by   = %s
        """, (oid, z, f, body.bagazo_sacarosa_pct, body.humedad_pct_bagazo, uid, uid))

        # LAB CAÑA
        cur.execute("""
            INSERT INTO daily_lab_cana
                (org_id, zafra_id, date, fibra_pct, entered_by)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                fibra_pct  = EXCLUDED.fibra_pct,
                updated_by = %s
        """, (oid, z, f, body.fibra_pct_cana, uid, uid))

        # JUGO RESIDUAL
        cur.execute("""
            INSERT INTO daily_lab_jugo_residual
                (org_id, zafra_id, date, brix, sacarosa_pct, entered_by)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                brix         = EXCLUDED.brix,
                sacarosa_pct = EXCLUDED.sacarosa_pct,
                updated_by   = %s
        """, (oid, z, f, body.jugo_residual_brix, body.jugo_residual_sacarosa_pct, uid, uid))

        # MIEL FINAL — sacarosa % + tons física + proceso
        cur.execute("""
            INSERT INTO daily_lab_miel_final
                (org_id, zafra_id, date,
                 sacarosa_pct, tons_fisica,
                 sacarosa_a_miel_final_tons, sacarosa_recuperable_tons,
                 entered_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                sacarosa_pct               = EXCLUDED.sacarosa_pct,
                tons_fisica                = EXCLUDED.tons_fisica,
                sacarosa_a_miel_final_tons = EXCLUDED.sacarosa_a_miel_final_tons,
                sacarosa_recuperable_tons  = EXCLUDED.sacarosa_recuperable_tons,
                updated_by                 = %s
        """, (oid, z, f,
              body.miel_final_sacarosa, body.miel_final_fisica_tons,
              body.sacarosa_a_miel_final_tons, body.sacarosa_recuperable_tons,
              uid, uid))

        # CACHAZA — filtro banda pol (sacarosa_pct) + tons medidas + % cachaza/caña
        cur.execute("""
            INSERT INTO daily_lab_cachaza
                (org_id, zafra_id, date, sacarosa_pct, tons, cachaza_pct_cana, entered_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                sacarosa_pct     = EXCLUDED.sacarosa_pct,
                tons             = EXCLUDED.tons,
                cachaza_pct_cana = EXCLUDED.cachaza_pct_cana,
                updated_by       = %s
        """, (oid, z, f, body.filtro_banda_pol, body.cachaza_dia_tons, body.cachaza_pct_cana, uid, uid))

        # PRODUCCION AZUCAR
        cur.execute("""
            INSERT INTO daily_produccion_azucar
                (org_id, zafra_id, date,
                 refinado_tons, refinado_pol_pct,
                 estandar_tons, estandar_pol_pct,
                 crudo_tons,    crudo_pol_pct,
                 entered_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (org_id, zafra_id, date) DO UPDATE SET
                refinado_tons    = EXCLUDED.refinado_tons,
                refinado_pol_pct = EXCLUDED.refinado_pol_pct,
                estandar_tons    = EXCLUDED.estandar_tons,
                estandar_pol_pct = EXCLUDED.estandar_pol_pct,
                crudo_tons       = EXCLUDED.crudo_tons,
                crudo_pol_pct    = EXCLUDED.crudo_pol_pct,
                updated_by       = %s
        """, (oid, z, f,
              body.refinado_tons, body.refinado_pol_pct,
              body.estandar_tons, body.estandar_pol_pct,
              body.crudo_tons,    body.crudo_pol_pct,
              uid, uid))

    return {"ok": True}
