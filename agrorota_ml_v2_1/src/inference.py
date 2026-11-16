from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
import joblib

from .features import load_integrated_dataset, build_feature_table, latest_feature_row
from .irrigation import weekly_irrigation_plan
from .rotation import recommend_rotations
from .diagnostics import generate_agronomic_alerts

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _calendar_phase(crop: str | None, date: pd.Timestamp, calendar_path: str | Path) -> tuple[str, str]:
    if not crop:
        return "cultivo actual no especificado", "no se puede asociar una fase del plano"
    cal = pd.read_csv(calendar_path, encoding="utf-8-sig").fillna("")
    row = cal[cal["cultivo"].astype(str).str.casefold() == crop.casefold()]
    if row.empty:
        return "sin fila en plano", "no hay calendario para el cultivo seleccionado"
    phase = str(row.iloc[0][MONTHS[date.month - 1]]).strip()
    if not phase:
        return "sin fase marcada para este mes", "el plano no marca una fase para el mes actual"
    names = {
        "siembra_directa": "siembra directa prevista",
        "almacigo": "almácigo previsto",
        "trasplante": "trasplante previsto",
        "cultivo": "cultivo/desarrollo previsto",
        "cosecha": "ventana de cosecha prevista",
    }
    return names.get(phase, phase), "fase del calendario mensual aproximado; no confirma el estado real"


def _vegetation_state(latest: pd.Series, history: pd.DataFrame) -> tuple[str, str]:
    ndvi = float(latest["NDVI_mean"])
    msi = float(latest["MSI_mean"])
    month = int(pd.Timestamp(latest["fecha"]).month)
    same_month = history[history["fecha"].dt.month == month]
    if len(same_month) < 5:
        same_month = history
    msi_q75 = float(same_month["MSI_mean"].quantile(0.75))
    ndvi_q20 = float(same_month["NDVI_mean"].quantile(0.20))
    ndvi_delta = latest.get("ndvi_change_per_day", np.nan)
    recent_low_rain = False
    p30 = latest.get("precip_30d_mm", np.nan)
    t30 = latest.get("temp_mean_30d_c", np.nan)
    if pd.notna(p30):
        rain_q25 = float(history.get("precip_30d_mm", pd.Series(dtype=float)).dropna().quantile(0.25)) if history.get("precip_30d_mm", pd.Series(dtype=float)).notna().any() else np.nan
        recent_low_rain = bool(pd.notna(rain_q25) and p30 <= rain_q25)
    ndvi_falling = bool(pd.notna(ndvi_delta) and ndvi_delta < -0.001)
    msi_high = msi >= msi_q75
    stress_signal = bool(msi_high and ndvi_falling and (recent_low_rain or (pd.notna(t30) and t30 > 25)))
    if stress_signal:
        return "posible estrés hídrico / vegetación en descenso", "alerta espectral relativa a la historia de la parcela; verificar humedad y estado en campo"
    if ndvi <= max(0.12, ndvi_q20):
        return "cobertura vegetal muy baja / posible suelo expuesto", "NDVI bajo no demuestra por sí solo ausencia de cultivo"
    if ndvi < 0.25:
        return "vegetación escasa", "interpretación de cobertura/vigor, no identifica especie ni fase"
    if ndvi < 0.45:
        return "vegetación moderada", "interpretación de cobertura/vigor, no identifica especie ni fase"
    return "vegetación densa / vigor espectral alto", "NDVI alto puede reflejar dosel denso; no confirma floración ni rendimiento"


def _vegetation_trend(latest: pd.Series) -> tuple[str, str]:
    delta = latest.get("ndvi_change_per_day", np.nan)
    if pd.isna(delta):
        return "tendencia no evaluable", "se necesitan al menos dos observaciones válidas"
    delta = float(delta)
    if delta > 0.001:
        return "crecimiento espectral (NDVI en aumento)", "indica aumento de cobertura/vigor; no confirma etapa fenológica"
    if delta < -0.001:
        return "descenso espectral (NDVI en caída)", "puede corresponder a senescencia, cosecha, estrés u otros factores; verificar en campo"
    return "vegetación relativamente estable", "cambio de NDVI pequeño entre observaciones válidas"


def _canonical_crop(crop: str | None, catalog_path: str | Path) -> str | None:
    if not crop:
        return None
    cat = pd.read_csv(catalog_path, encoding="utf-8-sig").fillna("")
    names = cat["Nombre_en_AgroRota"].astype(str)
    found = cat[names.str.casefold() == str(crop).casefold()]
    if not found.empty:
        return str(found.iloc[0]["Nombre_en_AgroRota"])
    aliases = {
        "naranja": "Naranja / cítricos", "citricos": "Naranja / cítricos", "cítricos": "Naranja / cítricos",
        "zapallo": "Zapallo coreano*", "calabaza": "Zapallo coreano*",
        "fresa": "Frutilla", "ciruelo": "Ciruelo (según catálogo: Spondias purpurea)",
        "ciruela": "Ciruelo (según catálogo: Spondias purpurea)",
    }
    canonical = aliases.get(str(crop).strip().casefold())
    return canonical if canonical in names.values else crop


def run_inference(
    dataset_path: str | Path,
    model_path: str | Path,
    reports_dir: str | Path,
    calendar_path: str | Path,
    catalog_path: str | Path,
    current_crop: str | None = None,
    weather_path: str | Path | None = None,
    forecast_path: str | Path | None = None,
    latitude: float | None = None,
    irrigation_phase: str | None = None,
):
    dataset = load_integrated_dataset(dataset_path)
    bundle = joblib.load(model_path)
    current_crop = _canonical_crop(current_crop, catalog_path)
    history = build_feature_table(dataset, min_pixel_fraction=bundle.get("min_pixel_fraction", 0.60))
    X_latest, latest = latest_feature_row(dataset, bundle["feature_columns"], bundle.get("min_pixel_fraction", 0.60))
    pred = bundle["model"].predict(X_latest)[0]
    ndvi_pred, msi_pred = float(pred[0]), float(pred[1])

    state, state_note = _vegetation_state(latest, history)
    trend, trend_note = _vegetation_trend(latest)
    today = pd.Timestamp.today().normalize()
    phase, phase_note = _calendar_phase(current_crop, today, calendar_path)
    latest_date = pd.Timestamp(latest["fecha"])

    # Alertas diferenciales de suelo, nutricion y sanidad. Son reglas de
    # cribado que priorizan verificaciones; no diagnostican causas.
    agronomic_alerts, agronomic_diagnostic = generate_agronomic_alerts(
        history,
        crop_stage=phase,
        soil_scenarios=("arenoso", "franco-limoso"),
    )
    days_old = int((pd.Timestamp.today().normalize() - latest_date).days)
    msi_month = history[history["fecha"].dt.month == latest_date.month]
    if len(msi_month) < 5:
        msi_month = history
    msi_q75 = float(msi_month["MSI_mean"].quantile(0.75))
    stress_signal = bool(
        pd.notna(latest.get("MSI_mean"))
        and float(latest["MSI_mean"]) >= msi_q75
        and pd.notna(latest.get("ndvi_change_per_day"))
        and float(latest["ndvi_change_per_day"]) < -0.001
    )
    recent_precip = latest.get("precip_30d_mm", np.nan)
    precip_series = history.get("precip_30d_mm", pd.Series(dtype=float)).dropna()
    dry_threshold = float(precip_series.quantile(0.25)) if not precip_series.empty else None
    latest_temp = latest.get("temp_mean_30d_c", np.nan)
    if pd.isna(latest_temp):
        latest_temp = latest.get("temp_mean_7d_c", np.nan)
    temp_for_rotation = float(latest_temp) if pd.notna(latest_temp) else None

    report_dir = Path(reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    status = {
        "fecha_consulta": str(today.date()),
        "fecha_referencia_calendario": str(today.date()),
        "fecha_ultima_imagen_valida": str(pd.Timestamp(latest["fecha"]).date()),
        "dias_desde_ultima_imagen_valida": days_old,
        "NDVI_observado": round(float(latest["NDVI_mean"]), 4),
        "MSI_observado": round(float(latest["MSI_mean"]), 4),
        "NDVI_predicho_siguiente_observacion": round(ndvi_pred, 4),
        "MSI_predicho_siguiente_observacion": round(msi_pred, 4),
        "horizonte_medio_dias_entre_observaciones_entrenamiento": round(float(bundle.get("median_horizon_days", np.nan)), 1),
        "estado_vegetacion": state,
        "interpretacion_estado": state_note,
        "tendencia_vegetacion": trend,
        "interpretacion_tendencia": trend_note,
        "fase_calendario": phase,
        "interpretacion_fase": phase_note,
        "floracion": "no inferible con los datos actuales; el plano no contiene una etapa de floración",
        "marchitez": "no confirmable con NDVI/MSI; se informa posible estrés, requiere inspección de campo",
        "materia_organica": "no medida; no inferir baja MO ni recomendar dosis de fertilizante desde NDVI/MSI/lluvia/temperatura",
        "nutrientes": "requiere análisis de suelo (MO, N, P, K, pH y conductividad eléctrica)",
        "calidad": f"NDVI_count={latest.get('NDVI_count', np.nan)}; MSI_count={latest.get('MSI_count', np.nan)}",
        "nota_modelo": "Random Forest estima el siguiente NDVI/MSI de una observación Sentinel válida; no predice cosecha, floración ni rendimiento.",
        "vigencia": "actual" if days_old <= 20 else ("observacion algo antigua" if days_old <= 45 else "observacion antigua; no usar como estado de hoy"),
        "metricas_test": bundle.get("metrics_test", {}),
        "diagnostico_agronomico": agronomic_diagnostic,
    }

    agronomic_alerts.to_csv(
        report_dir / "alertas_suelo_nutricion_sanidad.csv",
        index=False, encoding="utf-8-sig"
    )
    with open(report_dir / "diagnostico_agronomico.json", "w", encoding="utf-8") as f:
        json.dump(agronomic_diagnostic, f, ensure_ascii=False, indent=2)

    rotations = []
    for soil in ("arenoso", "franco-limoso"):
        rr = recommend_rotations(
            current_crop=current_crop,
            soil_scenario=soil,
            latest_temp_30d=temp_for_rotation,
            predicted_ndvi=ndvi_pred,
            predicted_msi=msi_pred,
            catalog_path=catalog_path,
            recent_precip_30d=float(recent_precip) if pd.notna(recent_precip) else None,
            dry_threshold_30d=dry_threshold,
            stress_signal=stress_signal,
        )
        rotations.append(rr)
    rotation_table = pd.concat(rotations, ignore_index=True)
    rotation_table.to_csv(report_dir / "comparacion_rotaciones.csv", index=False, encoding="utf-8-sig")

    irrigation_summary = []
    irrigation_files = []
    if weather_path and latitude is not None and current_crop:
        for soil in ("arenoso", "franco-limoso"):
            plan, meta = weekly_irrigation_plan(
                crop_name=current_crop,
                soil_scenario=soil,
                weather_path=weather_path,
                latitude_deg=latitude,
                catalog_path=catalog_path,
                calendar_path=calendar_path,
                forecast_path=forecast_path,
                phase_override=irrigation_phase,
            )
            plan.insert(0, "cultivo", current_crop)
            plan.insert(1, "escenario_suelo", soil)
            irrigation_files.append(plan)
            irrigation_summary.append(meta)
        pd.concat(irrigation_files, ignore_index=True).to_csv(
            report_dir / "plan_riego_7_dias.csv", index=False, encoding="utf-8-sig"
        )
        with open(report_dir / "resumen_riego_7_dias.json", "w", encoding="utf-8") as f:
            json.dump(irrigation_summary, f, ensure_ascii=False, indent=2, default=str)
    else:
        status["riego"] = "No calculado: se requiere cultivo actual, clima diario y latitud del centroide de la parcela."

    pd.DataFrame([status]).to_csv(report_dir / "estado_parcela_actual.csv", index=False, encoding="utf-8-sig")
    with open(report_dir / "estado_parcela_actual.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2, default=str)

    print("\nINFERENCIA AGRO ROTA")
    print("Última imagen válida:", status["fecha_ultima_imagen_valida"])
    print("NDVI / MSI observados:", status["NDVI_observado"], "/", status["MSI_observado"])
    print("NDVI / MSI siguiente observación (RF):", status["NDVI_predicho_siguiente_observacion"], "/", status["MSI_predicho_siguiente_observacion"])
    print("Estado de vegetación:", state)
    print("Fase del plano:", phase)
    print("Materia orgánica:", status["materia_organica"])
    print("Alertas agronómicas:", len(agronomic_alerts[agronomic_alerts["codigo"] != "SIN_ALERTAS_ESPECIFICAS"]))
    if not agronomic_alerts.empty:
        print(agronomic_alerts[["codigo", "nivel", "interpretacion_permitida"]].to_string(index=False))
    print("\nArchivos generados:", report_dir)
    if irrigation_summary:
        for m in irrigation_summary:
            print("Riego", m["suelo_escenario"], m["riego_semanal_neto_min_mm"], "a", m["riego_semanal_neto_max_mm"], "mm; fuente:", m["fuente_meteorologica"])
    return status, rotation_table
