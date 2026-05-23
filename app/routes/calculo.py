"""
calculo.py — Datos calculados y acumulados del balance de POL
"""
from fastapi import APIRouter, Depends
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user

router = APIRouter()


def _flt(row, key):
    if row is None:
        return None
    v = row.get(key)
    return float(v) if v is not None else None


@router.get("/dia")
def calculo_dia(fecha: date, zafra_id: str, user=Depends(get_current_user)):
    """Retorna datos diarios + acumulados (FECHA) para el balance de POL."""
    oid = user["org_id"]

    with get_db() as conn:
        cur = conn.cursor()

        def fetch(tabla):
            cur.execute(
                f"SELECT * FROM {tabla} WHERE org_id=%s AND zafra_id=%s AND date=%s",
                (oid, zafra_id, fecha),
            )
            r = cur.fetchone()
            return dict(r) if r else None

        molienda = fetch("daily_molienda")
        jm       = fetch("daily_lab_jugo_mezclado")
        bagazo   = fetch("daily_lab_bagazo")
        miel     = fetch("daily_lab_miel_final")
        cachaza  = fetch("daily_lab_cachaza")

        # SACAROSA APARENTE FECHA (TONS) = SUM(tons * sacarosa_pct / 100) hasta fecha
        cur.execute("""
            SELECT ROUND(SUM(tons * sacarosa_pct / 100)::numeric, 3) AS v
            FROM daily_lab_jugo_mezclado
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
              AND tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        sac_aparente_fecha = _flt(cur.fetchone(), "v")

        # BAGAZO DIA / FECHA TONS + SAC TONS — de pol_balance si ya fue calculado
        cur.execute("""
            SELECT tons_bagazo, perdida_bagazo_dia
            FROM daily_pol_balance
            WHERE org_id=%s AND zafra_id=%s AND date=%s
        """, (oid, zafra_id, fecha))
        pol = cur.fetchone()
        bagazo_dia_tons  = _flt(pol, "tons_bagazo")        if pol else None
        sac_bagazo_dia_t = _flt(pol, "perdida_bagazo_dia") if pol else None

        cur.execute("""
            SELECT ROUND(SUM(tons_bagazo)::numeric, 3) AS v
            FROM daily_pol_balance
            WHERE org_id=%s AND zafra_id=%s AND date<=%s AND tons_bagazo IS NOT NULL
        """, (oid, zafra_id, fecha))
        bagazo_fecha_tons = _flt(cur.fetchone(), "v")

        cur.execute("""
            SELECT ROUND(SUM(perdida_bagazo_dia)::numeric, 4) AS v
            FROM daily_pol_balance
            WHERE org_id=%s AND zafra_id=%s AND date<=%s AND perdida_bagazo_dia IS NOT NULL
        """, (oid, zafra_id, fecha))
        sac_bagazo_fecha_t = _flt(cur.fetchone(), "v")

        # SACAROSA BAGAZO % FECHA — promedio ponderado por caña molida bruta
        cur.execute("""
            SELECT ROUND(
                SUM(b.sacarosa_pct * m.cana_molida_bruta_tons)::numeric
                / NULLIF(SUM(m.cana_molida_bruta_tons), 0),
                4
            ) AS v
            FROM daily_lab_bagazo b
            JOIN daily_molienda m
              ON b.org_id = m.org_id AND b.zafra_id = m.zafra_id AND b.date = m.date
            WHERE b.org_id=%s AND b.zafra_id=%s AND b.date<=%s
              AND b.sacarosa_pct IS NOT NULL AND m.cana_molida_bruta_tons IS NOT NULL
        """, (oid, zafra_id, fecha))
        sac_bagazo_pct_fecha = _flt(cur.fetchone(), "v")

        return {
            "molienda":      molienda,
            "jugo_mezclado": jm,
            "bagazo":        bagazo,
            "miel_final":    miel,
            "cachaza":       cachaza,
            "calculado": {
                "sacarosa_aparente_fecha_tons": sac_aparente_fecha,
                "bagazo_dia_tons":              bagazo_dia_tons,
                "bagazo_fecha_tons":            bagazo_fecha_tons,
                "sac_bagazo_pct_fecha":         sac_bagazo_pct_fecha,
                "sac_bagazo_dia_tons":          sac_bagazo_dia_t,
                "sac_bagazo_fecha_tons":        sac_bagazo_fecha_t,
            },
        }
