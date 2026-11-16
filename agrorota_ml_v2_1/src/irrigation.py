from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

WEATHER_ALIASES = {
    "fecha": ["fecha", "date"],
    "precip_mm": ["precipitacion_mm_dia", "precipitacion", "PRECTOTCORR", "precip_mm"],
    "tmean": ["temperatura_media_c", "temperatura_media", "T2M", "tmean"],
    "tmax": ["temperatura_maxima_c", "temperatura_maxima", "T2M_MAX", "tmax"],
    "tmin": ["temperatura_minima_c", "temperatura_minima", "T2M_MIN", "tmin"],
}


def _norm(text):
    import unicodedata
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in text.lower() if ch.isalnum())


def load_weather(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No encuentro el clima diario NASA POWER: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    lookup = {_norm(c): c for c in df.columns}
    rename = {}
    for new, opts in WEATHER_ALIASES.items():
        for opt in opts:
            old = lookup.get(_norm(opt))
            if old is not None:
                rename[old] = new
                break
    df = df.rename(columns=rename)
    needed = ["fecha", "precip_mm", "tmean", "tmax", "tmin"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas del clima diario para riego: {missing}")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.normalize()
    for c in needed[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce").replace([-999, -999.0, -9999, -9999.0], np.nan)
    df = df.dropna(subset=["fecha"]).drop_duplicates("fecha").sort_values("fecha")
    return df.reset_index(drop=True)


def extraterrestrial_radiation_mj(latitude_deg: float, day_of_year: int) -> float:
    """FAO-56 extraterrestrial radiation Ra (MJ m-2 day-1)."""
    phi = math.radians(float(latitude_deg))
    j = int(day_of_year)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365.0)
    delta = 0.409 * math.sin(2 * math.pi * j / 365.0 - 1.39)
    arg = max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta)))
    ws = math.acos(arg)
    gsc = 0.0820
    ra = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.sin(ws)
    )
    return max(0.0, ra)


def hargreaves_eto(tmean: float, tmax: float, tmin: float, latitude_deg: float, day_of_year: int) -> float:
    """ETo estimada por Hargreaves-Samani, mm/día; no reemplaza calibración local."""
    vals = [tmean, tmax, tmin]
    if any(pd.isna(x) for x in vals) or tmax < tmin:
        return np.nan
    ra_mj = extraterrestrial_radiation_mj(latitude_deg, day_of_year)
    ra_mm = 0.408 * ra_mj
    eto = 0.0023 * (float(tmean) + 17.8) * math.sqrt(max(float(tmax) - float(tmin), 0.0)) * ra_mm
    return max(0.0, eto)


def _dayofyear_distance(a, b):
    d = abs(int(a) - int(b))
    return min(d, 366 - d)


def build_week_weather(weather: pd.DataFrame, start_date: pd.Timestamp, forecast_path: str | Path | None = None) -> tuple[pd.DataFrame, str]:
    dates = pd.date_range(start_date.normalize(), periods=7, freq="D")
    required = ["precip_mm", "tmean", "tmax", "tmin"]
    forecast_note = ""

    if forecast_path and Path(forecast_path).exists():
        forecast = load_weather(forecast_path).set_index("fecha")
        if all(d in forecast.index for d in dates):
            candidate = forecast.loc[dates].reset_index()
            if candidate[required].notna().all().all():
                return candidate, "pronostico_diario_proporcionado"
            forecast_note = "; pronostico_proporcionado_incompleto_se_usa_climatologia"
        else:
            forecast_note = "; pronostico_no_cubre_los_7_dias_se_usa_climatologia"

    # Sin pronóstico completo: climatología histórica, NO pronóstico meteorológico.
    hist = weather.copy()
    hist["doy"] = hist["fecha"].dt.dayofyear
    rows = []
    for d in dates:
        target_doy = d.dayofyear
        window = hist[hist["doy"].apply(lambda x: _dayofyear_distance(x, target_doy) <= 15)]
        if window.empty:
            window = hist[hist["fecha"].dt.month == d.month]

        # Variables por separado: una temperatura disponible no debe ocultar lluvia faltante.
        temp_window = window.dropna(subset=["tmean", "tmax", "tmin"])
        rain_window = window.dropna(subset=["precip_mm"])
        rows.append({
            "fecha": d,
            "precip_mm": float(rain_window["precip_mm"].mean()) if not rain_window.empty else np.nan,
            "tmean": float(temp_window["tmean"].mean()) if not temp_window.empty else np.nan,
            "tmax": float(temp_window["tmax"].mean()) if not temp_window.empty else np.nan,
            "tmin": float(temp_window["tmin"].mean()) if not temp_window.empty else np.nan,
        })
    source = "climatologia_historica_no_pronostico" + forecast_note
    return pd.DataFrame(rows), source


def _parse_kc(value):
    import re
    nums = re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", "."))
    if not nums:
        return None
    if "–" in str(value) or "-" in str(value) or len(nums) > 1:
        return (float(nums[0]), float(nums[1]))
    return (float(nums[0]), float(nums[0]))


def get_crop_record(crop_name: str, catalog_path: str | Path) -> dict:
    cat = pd.read_csv(catalog_path, encoding="utf-8-sig").fillna("")
    names = cat["Nombre_en_AgroRota"].astype(str)
    match = cat[names.str.casefold() == str(crop_name).casefold()]
    if match.empty:
        aliases = {
            "naranja": "Naranja / cítricos", "citricos": "Naranja / cítricos", "cítricos": "Naranja / cítricos",
            "zapallo": "Zapallo coreano*", "calabaza": "Zapallo coreano*",
            "fresa": "Frutilla", "ciruelo": "Ciruelo (según catálogo: Spondias purpurea)",
            "ciruela": "Ciruelo (según catálogo: Spondias purpurea)",
        }
        key = str(crop_name).strip().casefold()
        canonical = aliases.get(key)
        if canonical:
            match = cat[names.str.casefold() == canonical.casefold()]
    if match.empty:
        raise ValueError(f"Cultivo no incluido en el catálogo seleccionado: {crop_name}")
    return match.iloc[0].to_dict()


def _stage_for_date(crop_name: str, date: pd.Timestamp, calendar_path: str | Path, override: str | None):
    if override:
        return override, "fase_ingresada_por_usuario"
    cal = pd.read_csv(calendar_path, encoding="utf-8-sig").fillna("")
    row = cal[cal["cultivo"].astype(str).str.casefold() == crop_name.casefold()]
    if row.empty:
        return "cultivo", "fase_media_asumida_no_esta_en_el_plano"
    month_col = MONTHS[date.month - 1]
    phase = str(row.iloc[0][month_col]).strip()
    if not phase:
        return "cultivo", "fase_media_asumida_mes_sin_color_en_el_plano"
    if phase in ("siembra_directa", "almacigo", "trasplante"):
        return "inicio", "segun_plano_mensual_aproximado"
    if phase == "cultivo":
        return "medio", "segun_plano_mensual_aproximado"
    if phase == "cosecha":
        return "final", "segun_plano_mensual_aproximado"
    return "medio", "fase_no_reconocida_asumida_media"


def weekly_irrigation_plan(
    crop_name: str,
    soil_scenario: str,
    weather_path: str | Path,
    latitude_deg: float,
    catalog_path: str | Path,
    calendar_path: str | Path,
    start_date: pd.Timestamp | None = None,
    forecast_path: str | Path | None = None,
    phase_override: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    if not -66.5 <= float(latitude_deg) <= 66.5:
        raise ValueError("La latitud debe estar entre -66.5 y 66.5 grados para esta aproximación.")
    start_date = (start_date or (pd.Timestamp.today().normalize() + pd.Timedelta(days=1))).normalize()
    weather_hist = load_weather(weather_path)
    week, source = build_week_weather(weather_hist, start_date, forecast_path)
    crop = get_crop_record(crop_name, catalog_path)
    crop_name = crop["Nombre_en_AgroRota"]

    kc_col = {"inicio": "Kc_ini_FAO56", "medio": "Kc_mid_FAO56", "final": "Kc_end_FAO56"}
    daily = []
    for _, r in week.iterrows():
        phase, phase_source = _stage_for_date(crop_name, r["fecha"], calendar_path, phase_override)
        kc = _parse_kc(crop.get(kc_col[phase], ""))
        eto = hargreaves_eto(r["tmean"], r["tmax"], r["tmin"], latitude_deg, r["fecha"].dayofyear)
        if kc is None:
            etc_low = etc_high = np.nan
        else:
            etc_low = eto * kc[0] if pd.notna(eto) else np.nan
            etc_high = eto * kc[1] if pd.notna(eto) else np.nan
        # Aproximación simple de lluvia efectiva: 80% de la precipitación, limitada a ETc.
        # Se expone como supuesto de demo; no es balance calibrado del perfil de suelo.
        peff_low = min(max(0.0, 0.8 * float(r["precip_mm"])), etc_low) if pd.notna(etc_low) else np.nan
        peff_high = min(max(0.0, 0.8 * float(r["precip_mm"])), etc_high) if pd.notna(etc_high) else np.nan
        deficit_low = max(0.0, etc_low - peff_low) if pd.notna(etc_low) else np.nan
        deficit_high = max(0.0, etc_high - peff_high) if pd.notna(etc_high) else np.nan
        dias_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        daily.append({
            "fecha": r["fecha"], "dia": dias_es[r["fecha"].weekday()],
            "temperatura_media_c": r["tmean"],
            "temperatura_maxima_c": r["tmax"],
            "temperatura_minima_c": r["tmin"],
            "precipitacion_esperada_mm": r["precip_mm"],
            "ETo_Hargreaves_mm": eto,
            "fase_plano_o_asumida": phase,
            "origen_fase": phase_source,
            "Kc_min": kc[0] if kc else np.nan,
            "Kc_max": kc[1] if kc else np.nan,
            "ETc_min_mm": etc_low,
            "ETc_max_mm": etc_high,
            "lluvia_efectiva_aprox_min_mm": peff_low,
            "lluvia_efectiva_aprox_max_mm": peff_high,
            "deficit_neto_min_mm": deficit_low,
            "deficit_neto_max_mm": deficit_high,
        })
    df = pd.DataFrame(daily)

    # No convertir datos meteorológicos ausentes en cero: una lluvia desconocida
    # no equivale a ausencia de lluvia y no permite cerrar un balance semanal.
    missing_temp_days = int(df["ETo_Hargreaves_mm"].isna().sum())
    missing_rain_days = int(df["precipitacion_esperada_mm"].isna().sum())
    if missing_temp_days or missing_rain_days:
        df["riego_programado_min_mm"] = np.nan
        df["riego_programado_max_mm"] = np.nan
        meta = {
            "cultivo": crop_name,
            "suelo_escenario": soil_scenario,
            "fuente_meteorologica": source,
            "estado": "clima_incompleto_no_se_emite_recomendacion_numerica",
            "dias_sin_ETo": missing_temp_days,
            "dias_sin_precipitacion": missing_rain_days,
            "riego_semanal_neto_min_mm": None,
            "riego_semanal_neto_max_mm": None,
            "observacion": "Completar los datos diarios de temperatura y precipitación de los 7 días. No se reemplazaron faltantes por cero.",
        }
        return df, meta

    if soil_scenario == "arenoso":
        event_indices = [0, 2, 4, 6]  # 4 pulsos cortos como escenario operativo, no regla universal.
    elif soil_scenario == "franco-limoso":
        event_indices = [1, 3, 5]  # 3 pulsos como escenario operativo, no regla universal.
    else:
        raise ValueError("soil_scenario debe ser 'arenoso' o 'franco-limoso'.")

    low = df["deficit_neto_min_mm"].sum(min_count=7)
    high = df["deficit_neto_max_mm"].sum(min_count=7)
    if pd.isna(low) or pd.isna(high):
        meta = {
            "cultivo": crop_name,
            "suelo_escenario": soil_scenario,
            "fuente_meteorologica": source,
            "estado": "sin_Kc_citable_para_este_cultivo",
            "riego_semanal_neto_min_mm": None,
            "riego_semanal_neto_max_mm": None,
            "observacion": "No se calcula mm para este cultivo sin un Kc aplicable. El catálogo identifica Spondias purpurea; no se asume un Kc de ciruela europea.",
        }
        df["riego_programado_min_mm"] = np.nan
        df["riego_programado_max_mm"] = np.nan
        return df, meta

    n_events = len(event_indices)
    df["riego_programado_min_mm"] = 0.0
    df["riego_programado_max_mm"] = 0.0
    for i in event_indices:
        df.loc[i, "riego_programado_min_mm"] = low / n_events
        df.loc[i, "riego_programado_max_mm"] = high / n_events
    meta = {
        "cultivo": crop_name,
        "suelo_escenario": soil_scenario,
        "fuente_meteorologica": source,
        "estado": "estimacion_orientativa_no_orden_de_riego",
        "riego_semanal_neto_min_mm": round(float(low), 2),
        "riego_semanal_neto_max_mm": round(float(high), 2),
        "eventos_semana": n_events,
        "mm_a_litros_m2": "1 mm = 1 L/m2",
        "m3_ha_min": round(float(low) * 10, 1),
        "m3_ha_max": round(float(high) * 10, 1),
        "observacion": "Estimación con ETo Hargreaves, Kc FAO-56 y lluvia efectiva simplificada; falta capacidad de campo, punto de marchitez, profundidad efectiva, eficiencia y humedad medida del lote.",
    }
    return df, meta
