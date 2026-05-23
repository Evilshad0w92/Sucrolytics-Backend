"""
cordia.py — Vista "Corrida Diaria": pérdidas y balance de POL calculados
"""
from fastapi import APIRouter, Depends
from datetime import date
from app.database import get_db
from app.auth.dependencies import get_current_user

router = APIRouter()


def _f(row, key):
    if not row:
        return None
    v = row.get(key)
    return float(v) if v is not None else None


def _mul(a, b):
    return round(a * b / 100, 4) if (a is not None and b is not None) else None


@router.get("/ultimo-dia")
def cordia_ultimo_dia(zafra_id: str, user=Depends(get_current_user)):
    """Devuelve la fecha más reciente con datos de producción para la zafra."""
    oid = user["org_id"]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT MAX(date) AS ultima
            FROM daily_lab_jugo_mezclado
            WHERE org_id=%s AND zafra_id=%s AND tons IS NOT NULL
        """, (oid, zafra_id))
        r = cur.fetchone()
        d = dict(r) if r else {}
        return {"fecha": str(d["ultima"]) if d.get("ultima") else None}


@router.get("/dia")
def cordia_dia(fecha: date, zafra_id: str, user=Depends(get_current_user)):
    oid = user["org_id"]

    with get_db() as conn:
        cur = conn.cursor()

        def fetch(tabla):
            cur.execute(
                f"SELECT * FROM {tabla} WHERE org_id=%s AND zafra_id=%s AND date=%s",
                (oid, zafra_id, fecha),
            )
            r = cur.fetchone()
            return dict(r) if r else {}

        jm       = fetch("daily_lab_jugo_mezclado")
        miel     = fetch("daily_lab_miel_final")
        cachaza  = fetch("daily_lab_cachaza")
        prod     = fetch("daily_produccion_azucar")
        molienda = fetch("daily_molienda")
        cana_lab = fetch("daily_lab_cana")
        bagazo   = fetch("daily_lab_bagazo")
        jr       = fetch("daily_lab_jugo_residual")

        # Previous day's miel values for stock-delta calculations
        cur.execute("""
            SELECT tons_fisica, sacarosa_recuperable_tons
            FROM daily_lab_miel_final
            WHERE org_id=%s AND zafra_id=%s AND date < %s
            ORDER BY date DESC LIMIT 1
        """, (oid, zafra_id, fecha))
        prev_m = cur.fetchone()
        prev_m = dict(prev_m) if prev_m else {}
        prev_miel_fisica = _f(prev_m, "tons_fisica")               or 0.0
        prev_sac_rec     = _f(prev_m, "sacarosa_recuperable_tons") or 0.0

        # ── PERDIDAS DIA ──────────────────────────────────────────────────────

        # PERDIDA MIEL = SAC_APARENTE_MIEL + SAC_A_MIEL_FINAL_DIA
        # SAC_APARENTE_MIEL  = sacarosa_a_miel_final_tons (physical miel) × sac% / 100  (D218 = D203×D206/100)
        # SAC_A_MIEL_FINAL_DIA = tons_fisica (stock fecha) − yesterday's tons_fisica      (D375 = F375 − I375)
        # Fórmula Excel: D384 = D359 + D375
        sac_miel     = _mul(_f(miel, "sacarosa_a_miel_final_tons"), _f(miel, "sacarosa_pct"))
        sac_a_mf_dia = (_f(miel, "tons_fisica") or 0.0) - prev_miel_fisica
        perdida_miel_dia = round(sac_miel + sac_a_mf_dia, 4) if sac_miel is not None else None

        # PERDIDA CACHAZA = cachaza_tons × cachaza_sacarosa_pct / 100
        perdida_cachaza_dia = _mul(_f(cachaza, "tons"), _f(cachaza, "sacarosa_pct"))

        # AZUCAR P Y E = PRODUCCION_SAC + SAC_RECUPERABLE_DIA
        # SAC_RECUPERABLE_DIA = sacarosa_recuperable_tons (stock fecha) − yesterday's  (D373 = F373 − I373)
        # Fórmula Excel: D383 = D358 + D373
        ref = _mul(_f(prod, "refinado_tons"),  _f(prod, "refinado_pol_pct"))
        est = _mul(_f(prod, "estandar_tons"),  _f(prod, "estandar_pol_pct"))
        cru = _mul(_f(prod, "crudo_tons"),     _f(prod, "crudo_pol_pct"))
        partes = [x for x in [ref, est, cru] if x is not None]
        prod_pol = round(sum(partes), 4) if partes else None
        sac_rec_dia    = (_f(miel, "sacarosa_recuperable_tons") or 0.0) - prev_sac_rec
        azucar_pye_dia = round(prod_pol + sac_rec_dia, 4) if prod_pol is not None else None

        # JM SAC APARENTE DIA (parte de POL EN CAÑA — se completa después de calcular bagazo)
        jm_sac_dia = _mul(_f(jm, "tons"), _f(jm, "sacarosa_pct"))

        # PERDIDA BAGAZO
        # BAGAZO TONS = CANA MOLIDA + AGUA IMBIBICION - JM TONS
        # PERDIDA BAGAZO = BAGAZO TONS × BAGAZO SACAROSA% / 100
        perdida_bagazo_dia = None
        tons_baz_dia       = None
        baz_sac      = _f(bagazo, "sacarosa_pct")
        cana_for_baz = _f(molienda, "cana_molida_bruta_tons") or _f(molienda, "cana_recibida_tons")
        agua_baz     = _f(molienda, "agua_imbibicion_tons") or 0.0
        jm_tons_baz  = _f(jm, "tons")
        if all(v is not None for v in [cana_for_baz, jm_tons_baz, baz_sac]):
            tb = round(cana_for_baz + agua_baz - jm_tons_baz, 3)
            tons_baz_dia       = tb
            perdida_bagazo_dia = round(tb * baz_sac / 100, 4)

        # POL EN CAÑA = JM_SAC_APARENTE + BAGAZO_SAC_APARENTE
        # BAGAZO_SAC_APARENTE == perdida_bagazo_dia (misma fórmula: tons_baz × baz_sac / 100)
        pol_en_cana_dia = jm_sac_dia
        if perdida_bagazo_dia is not None and jm_sac_dia is not None:
            pol_en_cana_dia = round(jm_sac_dia + perdida_bagazo_dia, 4)

        # PERDIDAS TOTALES = POL EN CAÑA - AZUCAR P Y E
        perdidas_totales_dia = None
        if pol_en_cana_dia is not None and azucar_pye_dia is not None:
            perdidas_totales_dia = round(pol_en_cana_dia - azucar_pye_dia, 4)

        # PERDIDA INDETERMINADA = TOTALES - BAGAZO - MIEL - CACHAZA
        perdida_indet_dia = None
        if all(v is not None for v in [perdidas_totales_dia, perdida_bagazo_dia,
                                        perdida_miel_dia, perdida_cachaza_dia]):
            perdida_indet_dia = round(
                perdidas_totales_dia - perdida_bagazo_dia
                - perdida_miel_dia   - perdida_cachaza_dia, 4
            )

        # ── PÉRDIDAS / ACUMULADOS FECHA ───────────────────────────────────────

        def qsum(sql, params):
            cur.execute(sql, params)
            r = cur.fetchone()
            v = dict(r).get("v") if r else None
            return float(v) if v is not None else None

        # Carga inicial: valores I del Excel (FECHA del período anterior)
        try:
            for col, typ in [
                ("cana_fecha_anterior",    "NUMERIC(12,3)"),
                ("agua_fecha_anterior",    "NUMERIC(12,3)"),
                ("jm_tons_fecha_anterior", "NUMERIC(12,3)"),
            ]:
                cur.execute(f"ALTER TABLE zafra_inicial ADD COLUMN IF NOT EXISTS {col} {typ}")
            cur.execute("""
                SELECT COALESCE(jm_sac_fecha,      0) AS i53,
                       COALESCE(miel_sac_fecha,    0) AS i218,
                       COALESCE(cachaza_sac_fecha, 0) AS i94,
                       COALESCE(azucar_sac_fecha,  0) AS i290,
                       COALESCE(bagazo_sac_fecha,  0) AS i77,
                       COALESCE(cana_fecha_anterior,    0) AS i14,
                       COALESCE(agua_fecha_anterior,    0) AS i86,
                       COALESCE(jm_tons_fecha_anterior, 0) AS i40,
                       COALESCE(tons_fisica_anterior,          0) AS i375,
                       COALESCE(sacarosa_recuperable_anterior, 0) AS i373
                FROM zafra_inicial
                WHERE org_id = %s AND zafra_id = %s
            """, (oid, zafra_id))
            zi = cur.fetchone()
        except Exception:
            zi = None
        zi        = dict(zi) if zi else {}
        i53       = float(zi.get("i53")  or 0)   # JM SAC APARENTE FECHA anterior
        i218      = float(zi.get("i218") or 0)   # Miel SAC APARENTE FECHA anterior
        i94       = float(zi.get("i94")  or 0)   # Cachaza SAC APARENTE FECHA anterior
        i290      = float(zi.get("i290") or 0)   # Azúcar SAC APARENTE FECHA anterior
        i77  = float(zi.get("i77")  or 0)   # Bagazo SAC Aparente FECHA anterior
        i14  = float(zi.get("i14")  or 0)   # Caña Molida Bruta TONS FECHA anterior
        i86  = float(zi.get("i86")  or 0)   # Agua Imbibición TONS FECHA anterior
        i40  = float(zi.get("i40")  or 0)   # JM TONS FECHA anterior
        i375      = float(zi.get("i375") or 0)   # Stock SAC a miel final anterior
        i373      = float(zi.get("i373") or 0)   # Stock SAC recuperable anterior

        # Stocks FECHA actuales (para el cambio de stock acumulado)
        cur.execute("""
            SELECT COALESCE(tons_fisica, 0)               AS mf_fecha,
                   COALESCE(sacarosa_recuperable_tons, 0) AS sr_fecha
            FROM daily_lab_miel_final
            WHERE org_id = %s AND zafra_id = %s AND date <= %s
              AND sacarosa_a_miel_final_tons IS NOT NULL   -- sólo registros reales, no la carga inicial
            ORDER BY date DESC LIMIT 1
        """, (oid, zafra_id, fecha))
        fecha_row   = cur.fetchone()
        fecha_row   = dict(fecha_row) if fecha_row else {}
        mf_en_fecha = float(fecha_row.get("mf_fecha") or 0)
        sr_en_fecha = float(fecha_row.get("sr_fecha") or 0)

        # PERDIDA MIEL FECHA
        # = I218 (carry-forward) + SUM(SAC_APARENTE) + (F375_hoy − I375)
        perdida_miel_sac_fecha = qsum("""
            SELECT ROUND(SUM(sacarosa_a_miel_final_tons * sacarosa_pct / 100)::numeric, 4) AS v
            FROM daily_lab_miel_final
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
              AND sacarosa_a_miel_final_tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        perdida_miel_fecha = round(
            i218 + (perdida_miel_sac_fecha or 0) + (mf_en_fecha - i375), 4
        ) if perdida_miel_sac_fecha is not None else None

        # SAC APARENTE MIEL FECHA (card) = I218 + SUM(D218 de días ANTERIORES a fecha)
        # Usa date < fecha porque i218 ya incluye el período hasta ayer
        mf_sac_prev = qsum("""
            SELECT ROUND(SUM(sacarosa_a_miel_final_tons * sacarosa_pct / 100)::numeric, 4) AS v
            FROM daily_lab_miel_final
            WHERE org_id=%s AND zafra_id=%s AND date < %s
              AND sacarosa_a_miel_final_tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        mf_sac_fecha = round(i218 + (mf_sac_prev or 0), 4)

        # SAC APARENTE CACHAZA FECHA (card) = I94 + SUM(D94 de días ANTERIORES a fecha)
        cach_sac_prev = qsum("""
            SELECT ROUND(SUM(tons * sacarosa_pct / 100)::numeric, 4) AS v
            FROM daily_lab_cachaza
            WHERE org_id=%s AND zafra_id=%s AND date < %s
              AND tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        cach_sac_fecha = round(i94 + (cach_sac_prev or 0), 4)

        # PERDIDA CACHAZA FECHA = I94 + SUM(tons × sacarosa_pct / 100)
        perdida_cachaza_raw = qsum("""
            SELECT ROUND(SUM(tons * sacarosa_pct / 100)::numeric, 4) AS v
            FROM daily_lab_cachaza
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
              AND tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        perdida_cachaza_fecha = round(i94 + (perdida_cachaza_raw or 0), 4)

        # AZUCAR P Y E FECHA = I290 + SUM(prod_pol) + (F373_hoy − I373)
        prod_pol_fecha = qsum("""
            SELECT ROUND(SUM(
                COALESCE(refinado_tons * refinado_pol_pct, 0) +
                COALESCE(estandar_tons * estandar_pol_pct, 0) +
                COALESCE(crudo_tons    * crudo_pol_pct,    0)
            ) / 100::numeric, 4) AS v
            FROM daily_produccion_azucar
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
        """, (oid, zafra_id, fecha))
        azucar_pye_fecha = round(
            i290 + (prod_pol_fecha or 0) + (sr_en_fecha - i373), 4
        )

        # JM SAC APARENTE FECHA = I53 + SUM(tons × sacarosa_pct / 100)
        # Siempre se calcula (FECHA = I53 aunque no haya datos de producción aún)
        jm_sac_raw = qsum("""
            SELECT ROUND(SUM(tons * sacarosa_pct / 100)::numeric, 4) AS v
            FROM daily_lab_jugo_mezclado
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
              AND tons IS NOT NULL AND sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))
        jm_sac_fecha = round(i53 + (jm_sac_raw or 0), 4)

        # PERDIDA BAGAZO FECHA = I77 + SUM((CANA + AGUA - JM) × BAZ_SAC% / 100)
        perdida_bagazo_fecha = qsum("""
            SELECT ROUND(SUM(
                (COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons)
                 + COALESCE(m.agua_imbibicion_tons, 0) - jm.tons)
                * b.sacarosa_pct / 100
            )::numeric, 4) AS v
            FROM daily_molienda m
            JOIN daily_lab_jugo_mezclado jm
              ON jm.org_id=m.org_id AND jm.zafra_id=m.zafra_id AND jm.date=m.date
            JOIN daily_lab_bagazo b
              ON b.org_id=m.org_id AND b.zafra_id=m.zafra_id AND b.date=m.date
            WHERE m.org_id=%s AND m.zafra_id=%s AND m.date<=%s
              AND COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons) IS NOT NULL
              AND jm.tons IS NOT NULL AND b.sacarosa_pct IS NOT NULL
        """, (oid, zafra_id, fecha))

        # Aplica offset I77 al resultado del JOIN de bagazo
        if perdida_bagazo_fecha is not None:
            perdida_bagazo_fecha = round(i77 + perdida_bagazo_fecha, 4)

        # ── PRODUCIDO: toneladas físicas acumuladas (FECHA) ───────────────────

        baz_tons_raw = qsum("""
            SELECT ROUND(SUM(
                COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons)
                + COALESCE(m.agua_imbibicion_tons, 0) - jm.tons
            )::numeric, 3) AS v
            FROM daily_molienda m
            JOIN daily_lab_jugo_mezclado jm
              ON jm.org_id=m.org_id AND jm.zafra_id=m.zafra_id AND jm.date=m.date
            WHERE m.org_id=%s AND m.zafra_id=%s AND m.date<=%s
              AND COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons) IS NOT NULL
              AND jm.tons IS NOT NULL
        """, (oid, zafra_id, fecha))
        # F70 = (F14 + F86) - F40 = (I14 + SUM_CANA + I86 + SUM_AGUA) - (I40 + SUM_JM)
        #      = (I14 + I86 - I40) + baz_tons_raw
        i_baz_tons = i14 + i86 - i40
        baz_tons_fecha = round(i_baz_tons + (baz_tons_raw or 0), 3) if (i_baz_tons != 0 or baz_tons_raw is not None) else None

        mf_tons_fecha = qsum("""
            SELECT ROUND(SUM(sacarosa_a_miel_final_tons)::numeric, 3) AS v
            FROM daily_lab_miel_final
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
              AND sacarosa_a_miel_final_tons IS NOT NULL
        """, (oid, zafra_id, fecha))

        cach_tons_fecha = qsum("""
            SELECT ROUND(SUM(tons)::numeric, 3) AS v
            FROM daily_lab_cachaza
            WHERE org_id=%s AND zafra_id=%s AND date<=%s AND tons IS NOT NULL
        """, (oid, zafra_id, fecha))

        jm_tons_raw = qsum("""
            SELECT ROUND(SUM(tons)::numeric, 3) AS v
            FROM daily_lab_jugo_mezclado
            WHERE org_id=%s AND zafra_id=%s AND date<=%s AND tons IS NOT NULL
        """, (oid, zafra_id, fecha))
        jm_tons_fecha = round(i40 + (jm_tons_raw or 0), 3)

        cana_tons_raw = qsum("""
            SELECT ROUND(SUM(COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons))::numeric, 3) AS v
            FROM daily_molienda m
            JOIN daily_lab_jugo_mezclado jm
              ON jm.org_id=m.org_id AND jm.zafra_id=m.zafra_id AND jm.date=m.date
            WHERE m.org_id=%s AND m.zafra_id=%s AND m.date<=%s
              AND COALESCE(m.cana_molida_bruta_tons, m.cana_recibida_tons) IS NOT NULL
              AND jm.tons IS NOT NULL
        """, (oid, zafra_id, fecha))
        cana_tons_fecha = round(i14 + (cana_tons_raw or 0), 3) if (i14 or cana_tons_raw is not None) else None

        az_tons_fecha = qsum("""
            SELECT ROUND(SUM(
                COALESCE(refinado_tons, 0) +
                COALESCE(estandar_tons, 0) +
                COALESCE(crudo_tons, 0)
            )::numeric, 3) AS v
            FROM daily_produccion_azucar
            WHERE org_id=%s AND zafra_id=%s AND date<=%s
        """, (oid, zafra_id, fecha))

        partes_t = [x for x in [
            _f(prod, "refinado_tons"), _f(prod, "estandar_tons"), _f(prod, "crudo_tons")
        ] if x is not None]
        az_tons_dia = round(sum(partes_t), 3) if partes_t else None

        # ── AZUCAR TOTAL: SAC aparente ────────────────────────────────────────
        az_sac_dia = prod_pol

        # az_sac_fecha usa date < fecha (igual que mf/cach) porque i290 ya incluye el período actual
        prod_pol_prev = qsum("""
            SELECT ROUND(SUM(
                COALESCE(refinado_tons * refinado_pol_pct, 0) +
                COALESCE(estandar_tons * estandar_pol_pct, 0) +
                COALESCE(crudo_tons    * crudo_pol_pct,    0)
            ) / 100::numeric, 4) AS v
            FROM daily_produccion_azucar
            WHERE org_id=%s AND zafra_id=%s AND date < %s
        """, (oid, zafra_id, fecha))
        az_sac_fecha = round(i290 + (prod_pol_prev or 0), 4)

        # Variantes P Y E para PRODUCIDO Y ESTIMADO card
        # F384 = I218 + SUM(D359, date<fecha) + F375_absoluto
        # Se suma el stock absoluto actual (F375), no el delta (F375-I375)
        mf_sac_fecha_pe = round(mf_sac_fecha + (_f(miel, "tons_fisica") or 0), 4)
        az_sac_fecha_pe = round(az_sac_fecha + (_f(miel, "sacarosa_recuperable_tons") or 0), 4)

        # Indeterminados P Y E — aritmética de enteros para evitar error de punto flotante:
        # round(v, 3) luego *1000 → entero exacto, la resta es exacta, /1000 da 3dp correcto.
        def _i3(v):
            return round(round(v, 3) * 1000) if v is not None else None

        _ia = _i3(jm_sac_dia); _ib = _i3(azucar_pye_dia)
        _ic = _i3(perdida_miel_dia); _id = _i3(perdida_cachaza_dia)
        perdida_indet_dia_pe = ((_ia - _ib - _ic - _id) / 1000) \
            if all(x is not None for x in [_ia, _ib, _ic, _id]) else None

        # POL EN CAÑA FECHA = JM_SAC_FECHA + BAGAZO_SAC_FECHA
        pol_en_cana_fecha = jm_sac_fecha
        if perdida_bagazo_fecha is not None and jm_sac_fecha is not None:
            pol_en_cana_fecha = round(jm_sac_fecha + perdida_bagazo_fecha, 4)

        # Indeterminados P Y E FECHA — mismo enfoque de enteros
        # bagazo se cancela: pol_en_cana_fecha - bagazo = jm_sac_fecha
        _ja = _i3(jm_sac_fecha); _jb = _i3(az_sac_fecha_pe)
        _jc = _i3(mf_sac_fecha_pe); _jd = _i3(cach_sac_fecha)
        perdida_indet_fecha_pe = ((_ja - _jb - _jc - _jd) / 1000) \
            if all(x is not None for x in [_ja, _jb, _jc, _jd]) else None

        # PERDIDAS TOTALES FECHA = POL EN CAÑA FECHA - AZUCAR FECHA
        perdidas_totales_fecha = None
        if pol_en_cana_fecha is not None and azucar_pye_fecha is not None:
            perdidas_totales_fecha = round(pol_en_cana_fecha - azucar_pye_fecha, 4)

        # PERDIDA INDET FECHA
        perdida_indet_fecha = None
        if all(v is not None for v in [perdidas_totales_fecha, perdida_bagazo_fecha,
                                        perdida_miel_fecha, perdida_cachaza_fecha]):
            perdida_indet_fecha = round(
                perdidas_totales_fecha - perdida_bagazo_fecha
                - perdida_miel_fecha   - perdida_cachaza_fecha, 4
            )

        baz_sac_pct_fecha = round(perdida_bagazo_fecha / baz_tons_fecha * 100, 3) \
            if (perdida_bagazo_fecha is not None and baz_tons_fecha and baz_tons_fecha != 0) else None

        return {
            "perdida_bagazo_dia":     perdida_bagazo_dia,
            "perdida_bagazo_fecha":   perdida_bagazo_fecha,
            "perdida_miel_dia":       perdida_miel_dia,
            "perdida_miel_fecha":     perdida_miel_fecha,
            "perdida_cachaza_dia":    perdida_cachaza_dia,
            "perdida_cachaza_fecha":  perdida_cachaza_fecha,
            "perdida_indet_dia":      perdida_indet_dia,
            "perdida_indet_fecha":    perdida_indet_fecha,
            "perdidas_totales_dia":   perdidas_totales_dia,
            "perdidas_totales_fecha": perdidas_totales_fecha,
            "azucar_pye_dia":         azucar_pye_dia,
            "azucar_pye_fecha":       azucar_pye_fecha,
            "pol_en_cana_dia":        pol_en_cana_dia,
            "pol_en_cana_fecha":      pol_en_cana_fecha,
            # Molienda
            "cana_molida_dia":        _f(molienda, "cana_molida_bruta_tons") or _f(molienda, "cana_recibida_tons"),
            # Bagazo detalle
            "baz_sac_pct_dia":        baz_sac,
            "baz_sac_pct_fecha":      baz_sac_pct_fecha,
            # Proceso — stocks miel final (usa el registro de HOY directamente)
            "mf_stock_dia":           round(sac_a_mf_dia, 4) if _f(miel, "tons_fisica") is not None else None,
            "mf_stock_fecha":         _f(miel, "tons_fisica"),
            "sr_stock_dia":           round(sac_rec_dia, 4) if _f(miel, "sacarosa_recuperable_tons") is not None else None,
            "sr_stock_fecha":         _f(miel, "sacarosa_recuperable_tons"),
            # PRODUCIDO Y ESTIMADO (toneladas físicas)
            "baz_tons_dia":           tons_baz_dia,
            "baz_tons_fecha":         baz_tons_fecha,
            "mf_tons_dia":            _f(miel, "sacarosa_a_miel_final_tons"),
            "mf_tons_fecha":          mf_tons_fecha,
            "cach_tons_dia":          _f(cachaza, "tons"),
            "cach_tons_fecha":        cach_tons_fecha,
            "cana_tons_dia":          _f(molienda, "cana_molida_bruta_tons") or _f(molienda, "cana_recibida_tons"),
            "cana_tons_fecha":        cana_tons_fecha,
            "jm_tons_dia":            _f(jm, "tons"),
            "jm_tons_fecha":          jm_tons_fecha,
            "az_tons_dia":            az_tons_dia,
            "az_tons_fecha":          az_tons_fecha,
            # AZUCAR TOTAL (SAC aparente)
            "az_sac_dia":             az_sac_dia,
            "az_sac_fecha":           az_sac_fecha,
            "az_sac_fecha_pe":        az_sac_fecha_pe,
            # Jugo Mezclado (raw + computed)
            "jm_sac_pct_dia":         _f(jm, "sacarosa_pct"),
            "jm_sac_dia":             jm_sac_dia,
            "jm_sac_fecha":           jm_sac_fecha,
            # Miel Final (detalle card)
            "mf_sac_pct_dia":         _f(miel, "sacarosa_pct"),
            "mf_fisica_dia":          _f(miel, "sacarosa_a_miel_final_tons"),
            "mf_sac_dia":             sac_miel,
            "mf_sac_fecha":           mf_sac_fecha,
            "mf_sac_fecha_pe":        mf_sac_fecha_pe,
            "perdida_indet_dia_pe":   perdida_indet_dia_pe,
            "perdida_indet_fecha_pe": perdida_indet_fecha_pe,
            # Cachaza (detalle card)
            "cach_sac_pct_dia":       _f(cachaza, "sacarosa_pct"),
            "cach_sac_dia":           perdida_cachaza_dia,
            "cach_sac_fecha":         cach_sac_fecha,
            # Azúcar por tipo (DIA)
            "ref_tons_dia":           _f(prod, "refinado_tons"),
            "ref_pol_pct_dia":        _f(prod, "refinado_pol_pct"),
            "ref_sac_dia":            ref,
            "est_tons_dia":           _f(prod, "estandar_tons"),
            "est_pol_pct_dia":        _f(prod, "estandar_pol_pct"),
            "est_sac_dia":            est,
            "cru_tons_dia":           _f(prod, "crudo_tons"),
            "cru_pol_pct_dia":        _f(prod, "crudo_pol_pct"),
            "cru_sac_dia":            cru,
        }
