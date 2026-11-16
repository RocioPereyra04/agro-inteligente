from __future__ import annotations

"""Alertas diferenciales de suelo, nutricion y sanidad.

Este modulo NO diagnostica compactacion, deficiencias, lixiviacion ni patogenos.
Combina tendencias de NDVI/MSI con contexto meteorologico para priorizar
inspecciones de campo. Los umbrales se calculan principalmente con percentiles
historicos de la propia parcela y no son umbrales fisiologicos universales.
"""

import numpy as np
import pandas as pd


ALERT_COLUMNS = [
    "codigo", "categoria", "nivel", "indicador", "evidencia_observada",
    "interpretacion_permitida", "causas_posibles_no_confirmadas",
    "verificacion_recomendada", "localizacion", "confianza",
]


def _num(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else np.nan
    except (TypeError, ValueError):
        return np.nan


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()


def _q(series: pd.Series, quantile: float, default=np.nan) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.quantile(quantile)) if len(s) >= 8 else float(default)


def _slope_per_day(df: pd.DataFrame, column: str, n: int = 4) -> float:
    if column not in df.columns or "fecha" not in df.columns:
        return np.nan
    part = df[["fecha", column]].dropna().tail(n)
    if len(part) < 3:
        return np.nan
    x = (part["fecha"] - part["fecha"].iloc[0]).dt.days.to_numpy(dtype=float)
    y = pd.to_numeric(part[column], errors="coerce").to_numpy(dtype=float)
    if len(np.unique(x)) < 2 or not np.isfinite(y).all():
        return np.nan
    return float(np.polyfit(x, y, 1)[0])


def _add(rows, **kwargs):
    defaults = {
        "codigo": "", "categoria": "", "nivel": "revision",
        "indicador": "", "evidencia_observada": "",
        "interpretacion_permitida": "",
        "causas_posibles_no_confirmadas": "",
        "verificacion_recomendada": "",
        "localizacion": "No localizable: se usan estadísticas agregadas de toda la parcela.",
        "confianza": "baja",
    }
    defaults.update(kwargs)
    rows.append(defaults)


def generate_agronomic_alerts(
    history: pd.DataFrame,
    crop_stage: str | None = None,
    soil_scenarios: tuple[str, ...] = ("arenoso", "franco-limoso"),
) -> tuple[pd.DataFrame, dict]:
    """Genera alertas prudentes a partir de la serie válida de una parcela.

    Entradas esperadas: salida de build_feature_table(), con columnas fecha,
    NDVI_mean, MSI_mean, precip_7d_mm y temperatura media 7d cuando existan.
    """
    if history.empty:
        raise ValueError("No hay observaciones válidas para el diagnóstico diferencial.")

    df = history.copy().sort_values("fecha").reset_index(drop=True)
    latest = df.iloc[-1]
    rows: list[dict] = []
    warnings: list[str] = []

    ndvi = _num(latest.get("NDVI_mean"))
    msi = _num(latest.get("MSI_mean"))
    rain7 = _num(latest.get("precip_7d_mm"))
    rain30 = _num(latest.get("precip_30d_mm"))
    temp7 = _num(latest.get("temp_mean_7d_c"))

    # Los umbrales se calculan con el historial anterior al bloque más reciente
    # para evitar que el propio episodio sospechoso eleve sus umbrales.
    exclude_n = max(1, min(4, len(df) // 5))
    reference = df.iloc[:-exclude_n] if len(df) > exclude_n + 5 else df.iloc[:-1]
    if reference.empty:
        reference = df
    rain_hist = _series(reference, "precip_7d_mm")
    rain_q25 = _q(rain_hist, 0.25)
    rain_q50 = _q(rain_hist, 0.50)
    rain_q75 = _q(rain_hist, 0.75)
    rain_q90 = _q(rain_hist, 0.90)
    rain_q95 = _q(rain_hist, 0.95)

    month_df = reference[reference["fecha"].dt.month == pd.Timestamp(latest["fecha"]).month]
    baseline = month_df if len(month_df) >= 5 else df
    ndvi_q20 = _q(_series(baseline, "NDVI_mean"), 0.20)
    msi_q75 = _q(_series(baseline, "MSI_mean"), 0.75)

    ndvi_slope = _slope_per_day(df, "NDVI_mean", n=4)
    msi_slope = _slope_per_day(df, "MSI_mean", n=4)
    ndvi_changes = _series(reference.tail(24), "ndvi_change_per_day")
    msi_changes = _series(reference.tail(24), "msi_change_per_day")
    ndvi_drop_cut = min(-0.0003, _q(ndvi_changes, 0.10, default=-0.0003))
    msi_rise_cut = max(0.0003, _q(msi_changes, 0.90, default=0.0003))

    rain_not_low = pd.notna(rain7) and pd.notna(rain_q25) and rain7 > rain_q25
    rain_normal_or_high = pd.notna(rain7) and pd.notna(rain_q50) and rain7 >= rain_q50
    ndvi_falling = pd.notna(ndvi_slope) and ndvi_slope < ndvi_drop_cut
    msi_rising = pd.notna(msi_slope) and msi_slope > msi_rise_cut
    msi_not_elevated = pd.notna(msi) and pd.notna(msi_q75) and msi <= msi_q75

    # 1) Firma combinada: descenso de NDVI + ascenso de MSI tras lluvia no baja.
    recent = df.tail(6).copy()
    required = {"ndvi_change_per_day", "msi_change_per_day", "precip_7d_mm"}
    if required.issubset(recent.columns) and pd.notna(rain_q50):
        events = (
            (pd.to_numeric(recent["ndvi_change_per_day"], errors="coerce") < ndvi_drop_cut)
            & (pd.to_numeric(recent["msi_change_per_day"], errors="coerce") > msi_rise_cut)
            & (pd.to_numeric(recent["precip_7d_mm"], errors="coerce") >= rain_q50)
        )
        recurrent_events = int(events.sum())
    else:
        recurrent_events = 0

    if ndvi_falling and msi_rising and rain_normal_or_high:
        recurrence_text = (
            f"Patrón combinado observado en {recurrent_events} de las últimas {len(recent)} observaciones válidas. "
            if recurrent_events else "Patrón combinado detectado en la tendencia reciente. "
        )
        _add(
            rows,
            codigo="ESTRES_CON_LLUVIA",
            categoria="suelo_raices_sanidad",
            nivel="alta_revision" if recurrent_events >= 2 else "revision",
            indicador="NDVI descendente + MSI ascendente + precipitación reciente no baja",
            evidencia_observada=(
                recurrence_text
                + f"Pendiente NDVI={ndvi_slope:.5f}/día; pendiente MSI={msi_slope:.5f}/día; "
                + f"precipitación 7d={rain7:.1f} mm."
            ),
            interpretacion_permitida="Hay una señal de estrés de la vegetación que no queda explicada simplemente por poca lluvia regional.",
            causas_posibles_no_confirmadas=(
                "Restricción de raíces/compactación o tosca, anegamiento o drenaje deficiente, "
                "salinidad, nematodos, enfermedades radiculares/vasculares, daño mecánico o etapa fenológica."
            ),
            verificacion_recomendada=(
                "Inspeccionar plantas y raíces en varios puntos; abrir calicatas; comprobar drenaje y humedad del perfil; "
                "revisar cuello y vasos; comparar con una zona sana. No aplicar fungicida ni descompactar solo por esta alerta."
            ),
            confianza="baja: indicio espectral y clima regional; causas no separables con estos datos",
        )

    # 2) Posible restricción física recurrente. Nunca se etiqueta como compactación confirmada.
    if recurrent_events >= 2:
        _add(
            rows,
            codigo="POSIBLE_RESTRICCION_FISICA",
            categoria="suelo",
            nivel="alta_revision",
            indicador="Repetición de NDVI↓ y MSI↑ tras períodos con precipitación 7d igual/superior a la mediana histórica",
            evidencia_observada=f"Se repitió el patrón en {recurrent_events} de las últimas {len(recent)} observaciones válidas.",
            interpretacion_permitida="Patrón compatible con una limitación de la zona radicular; no demuestra piso de arado, tosca ni capa arcillosa.",
            causas_posibles_no_confirmadas="Compactación, horizonte petrocálcico/tosca, capa arcillosa densa, drenaje, salinidad o problemas radiculares.",
            verificacion_recomendada=(
                "Realizar calicata y observar profundidad/forma de raíces. Medir resistencia con penetrómetro en humedad próxima a capacidad de campo "
                "y comparar transectas de zonas afectadas y de referencia. Registrar profundidad y espesor de la capa."
            ),
            confianza="baja; patrón repetido pero sin medición física del perfil",
        )

    # 3) Bajo vigor con MSI no elevado: abre un diagnóstico diferencial, no diagnostica nutrientes.
    stage_text = str(crop_stage or "").casefold()
    early_stage = any(token in stage_text for token in ("siembra", "almacigo", "almácigo", "trasplante"))
    low_vigor = pd.notna(ndvi) and pd.notna(ndvi_q20) and ndvi <= ndvi_q20
    if low_vigor and msi_not_elevated and rain_not_low and not early_stage:
        _add(
            rows,
            codigo="BAJO_VIGOR_NO_EXPLICADO_POR_SEQUIA",
            categoria="nutricion_suelo",
            nivel="revision",
            indicador="NDVI bajo respecto de la historia de la parcela; MSI no elevado; precipitación 7d por encima del cuartil inferior",
            evidencia_observada=(
                f"NDVI={ndvi:.3f} (referencia estacional Q20={ndvi_q20:.3f}); "
                f"MSI={msi:.3f} (Q75 estacional={msi_q75:.3f}); precipitación 7d={rain7:.1f} mm."
            ),
            interpretacion_permitida=(
                "El patrón no muestra una señal clara de estrés hídrico foliar según el MSI relativo. "
                "Conviene revisar nutrición y otras causas de bajo vigor."
            ),
            causas_posibles_no_confirmadas=(
                "Deficiencia o desequilibrio nutricional (N, P, K u otros), pH inadecuado, salinidad, "
                "compactación, raíz/enfermedad, malezas, daño de manejo, suelo expuesto o desfase fenológico."
            ),
            verificacion_recomendada=(
                "Tomar muestras de suelo por zonas para MO, pH, conductividad eléctrica, N disponible, P y K; "
                "complementar con análisis foliar de acuerdo con el cultivo y la etapa. No prescribir fertilizante por NDVI/MSI únicamente."
            ),
            confianza="baja a media como señal de revisión; muy baja para identificar el nutriente",
        )

    # 4) Riesgo potencial de lixiviación: lluvia extrema relativa + textura arenosa.
    extreme_rain = pd.notna(rain7) and pd.notna(rain_q95) and rain_q95 > 0 and rain7 >= rain_q95
    sandy_scenario = any("aren" in str(s).casefold() for s in soil_scenarios)
    if extreme_rain and sandy_scenario:
        _add(
            rows,
            codigo="RIESGO_POTENCIAL_LIXIVIACION",
            categoria="nutricion_agua",
            nivel="revision",
            indicador="Precipitación acumulada 7d en el extremo superior de la distribución histórica (Q95) y escenario arenoso",
            evidencia_observada=f"Precipitación 7d={rain7:.1f} mm; umbral histórico Q95={rain_q95:.1f} mm.",
            interpretacion_permitida=(
                "Hubo un evento húmedo regional que podría aumentar el movimiento de nitratos si había nitrógeno mineral disponible "
                "y el agua percoló por debajo de las raíces. No se detecta ni cuantifica nitrato lavado."
            ),
            causas_posibles_no_confirmadas="Drenaje profundo, textura y estructura reales, dosis/fecha de fertilización, riego y absorción del cultivo.",
            verificacion_recomendada=(
                "Revisar fecha y dosis de fertilización nitrogenada; medir nitrato residual por profundidad o analizar agua de drenaje. "
                "Si no hubo fertilización ni nitrato disponible, no atribuir pérdida de N."
            ),
            confianza="baja: riesgo condicionado; lluvia NASA POWER es regional y no mide percolación del lote",
        )

    # 5) Condiciones para vigilancia sanitaria general; no es un modelo epidemiológico.
    wet_weather = pd.notna(rain7) and pd.notna(rain_q75) and rain7 >= rain_q75
    temp_in_broad_band = pd.notna(temp7) and 12.0 <= temp7 <= 28.0
    if wet_weather and temp_in_broad_band:
        _add(
            rows,
            codigo="VIGILANCIA_SANITARIA_CLIMATICA",
            categoria="sanidad",
            nivel="revision",
            indicador="Precipitación 7d alta respecto de la historia y temperatura media 7d en una banda amplia de vigilancia",
            evidencia_observada=f"Precipitación 7d={rain7:.1f} mm (Q75={rain_q75:.1f} mm); temperatura media 7d={temp7:.1f} °C.",
            interpretacion_permitida=(
                "Las condiciones regionales justifican intensificar la observación de hojas, frutos, cuello y raíces. "
                "No se calcula infección ni probabilidad de una enfermedad concreta."
            ),
            causas_posibles_no_confirmadas="Patógenos foliares o de suelo específicos del cultivo, humedad del dosel, densidad de plantación y presencia de inóculo.",
            verificacion_recomendada=(
                "Inspeccionar el cultivo y registrar síntomas, etapa y distribución. Para un modelo epidemiológico específico incorporar "
                "humedad relativa y horas de mojado foliar (idealmente horarias), además del patógeno y cultivar susceptibles."
            ),
            confianza="baja: filtro climático exploratorio, no modelo fitopatológico",
        )

    # 6) Estado explícito de datos que no existen en el pipeline.
    missing_inputs = [
        "humedad relativa y horas de mojado foliar",
        "humedad del suelo medida por profundidad",
        "análisis de MO, N, P, K, pH y conductividad eléctrica",
        "resistencia a la penetración/perfil de suelo",
        "fecha y dosis de fertilización e historial fitosanitario",
        "imágenes/estadísticas por subzona para localizar manchones",
    ]
    if not rows:
        _add(
            rows,
            codigo="SIN_ALERTAS_ESPECIFICAS",
            categoria="estado_general",
            nivel="informativo",
            indicador="No se activaron las reglas exploratorias con los últimos datos disponibles",
            evidencia_observada=f"NDVI={ndvi}; MSI={msi}; precipitación 7d={rain7}; temperatura media 7d={temp7}.",
            interpretacion_permitida="No activar una regla no demuestra ausencia de compactación, deficiencia, lixiviación o enfermedad.",
            causas_posibles_no_confirmadas="Puede haber problemas no visibles para los índices o que no coincidan con las reglas actuales.",
            verificacion_recomendada="Mantener recorridas periódicas y realizar análisis de suelo cuando corresponda.",
            confianza="no aplica",
        )

    alerts = pd.DataFrame(rows, columns=ALERT_COLUMNS)
    summary = {
        "fecha_ultima_observacion": str(pd.Timestamp(latest["fecha"]).date()),
        "numero_alertas": int(len(alerts[alerts["codigo"] != "SIN_ALERTAS_ESPECIFICAS"])),
        "pendientes_de_datos": missing_inputs,
        "umbrales": {
            "precipitacion_7d_Q25_mm": None if pd.isna(rain_q25) else round(rain_q25, 2),
            "precipitacion_7d_Q50_mm": None if pd.isna(rain_q50) else round(rain_q50, 2),
            "precipitacion_7d_Q75_mm": None if pd.isna(rain_q75) else round(rain_q75, 2),
            "precipitacion_7d_Q95_mm": None if pd.isna(rain_q95) else round(rain_q95, 2),
            "NDVI_Q20_estacional_mm": None if pd.isna(ndvi_q20) else round(ndvi_q20, 4),
            "MSI_Q75_estacional": None if pd.isna(msi_q75) else round(msi_q75, 4),
        },
        "limitaciones": [
            "MSI B11/B8 es un indicador espectral del contenido hídrico de la vegetación/canopia, no una medición directa del agua del suelo.",
            "NASA POWER meteorológico tiene una grilla regional (aprox. 0,5 x 0,625 grados en la documentación actual); no representa lluvia exacta en cada punto del lote.",
            "El dataset integrado contiene estadísticas agregadas de la parcela; estas alertas no localizan zonas dentro del polígono.",
            "NDVI/MSI no identifican por sí solos una causa única de estrés ni identifican el patógeno o nutriente responsable.",
        ],
        "nota": "Alertas exploratorias de apoyo al monitoreo; no constituyen diagnósticos ni recomendaciones de fertilización o control fitosanitario.",
    }
    return alerts, summary
