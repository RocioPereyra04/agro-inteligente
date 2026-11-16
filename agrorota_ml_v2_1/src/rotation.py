from __future__ import annotations

from pathlib import Path
import re
import numpy as np
import pandas as pd


def _float_range(text):
    nums = re.findall(r"\d+(?:[.,]\d+)?", str(text).replace(",", "."))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), float(nums[0])
    return None


def _water_score(text):
    t = str(text).casefold()
    if "muy alta" in t:
        return 20
    if "alta" in t and "media-alta" not in t:
        return 35
    if "media-alta" in t or "media alta" in t:
        return 55
    if "media" in t:
        return 72
    if "baja" in t:
        return 90
    return 50


def _nutrient_score(text):
    t = str(text).casefold()
    if "baja" in t:
        return 90
    if "media-baja" in t or "media baja" in t:
        return 82
    if "media-alta" in t or "media alta" in t:
        return 55
    if "alta" in t:
        return 40
    if "media" in t:
        return 70
    if "fijadora" in t:
        return 85
    return 55


def _root_score(text):
    t = str(text).casefold()
    if "muy profunda" in t:
        return 95
    if "profunda" in t and "media" in t:
        return 85
    if "profunda" in t:
        return 88
    if "media-profunda" in t or "media profunda" in t:
        return 80
    if "media" in t:
        return 62
    if "superficial" in t:
        return 38
    return 55


def _soil_texture_score(rec_text: str, soil: str) -> int:
    t = str(rec_text).casefold()
    if soil == "arenoso":
        if "arenoso" in t:
            return 90
        if "franco" in t:
            return 65
        return 40
    if soil == "franco-limoso":
        if "franco-limoso" in t or "franco limoso" in t:
            return 90
        if "franco a franco" in t or "franco" in t:
            return 70
        return 45
    return 50


def _is_mo_sensitive(soil_text: str) -> bool:
    return "rico en mo" in str(soil_text).casefold() or "alta mo" in str(soil_text).casefold()


def _temperature_fit(temp_c, optimum_text):
    bounds = _float_range(optimum_text)
    if bounds is None or pd.isna(temp_c):
        return 50, "temperatura_no_evaluable"
    low, high = bounds
    if low <= float(temp_c) <= high:
        return 100, "dentro_del_rango_optimo_del_catalogo"
    distance = low - float(temp_c) if float(temp_c) < low else float(temp_c) - high
    if distance <= 3:
        return 75, "cerca_del_rango_optimo_del_catalogo"
    if distance <= 7:
        return 45, "fuera_del_rango_optimo_del_catalogo"
    return 20, "muy_fuera_del_rango_optimo_del_catalogo"


def _normalise_crop(text):
    t = str(text).casefold()
    mapping = {
        "lechuga": "Lechuga",
        "zapallo": "Zapallo coreano*",
        "calabaza": "Zapallo coreano*",
        "frutilla": "Frutilla",
        "fresa": "Frutilla",
        "naranja": "Naranja / cítricos",
        "citricos": "Naranja / cítricos",
        "cítricos": "Naranja / cítricos",
        "melon": "Melón",
        "melón": "Melón",
        "sandia": "Sandía",
        "sandía": "Sandía",
        "ciruela": "Ciruelo (según catálogo: Spondias purpurea)",
        "ciruelo": "Ciruelo (según catálogo: Spondias purpurea)",
    }
    for key, value in mapping.items():
        if key in t:
            return value
    return None


def recommend_rotations(
    current_crop: str | None,
    soil_scenario: str,
    latest_temp_30d: float | None,
    predicted_ndvi: float | None,
    predicted_msi: float | None,
    catalog_path: str | Path,
    recent_precip_30d: float | None = None,
    dry_threshold_30d: float | None = None,
    stress_signal: bool = False,
) -> pd.DataFrame:
    cat = pd.read_csv(catalog_path, encoding="utf-8-sig").fillna("")
    current = _normalise_crop(current_crop) if current_crop else None
    current_row = cat[cat["Nombre_en_AgroRota"] == current]
    current_family = str(current_row.iloc[0]["Familia Botánica"]) if not current_row.empty else None
    current_perennial = (
        str(current_row.iloc[0]["Tipo_sistema"]) == "frutal_perenne"
        if not current_row.empty else False
    )
    dry_context = (
        recent_precip_30d is not None
        and dry_threshold_30d is not None
        and recent_precip_30d <= dry_threshold_30d
    )

    # Proxies explícitos, no mediciones de mejora del suelo.
    if predicted_ndvi is not None and predicted_msi is not None:
        if predicted_ndvi < 0.15:
            condition_note = "vegetación proyectada muy baja; verificar cobertura real"
        elif predicted_msi > 1.2:
            condition_note = "MSI proyectado elevado; revisar posible estrés antes de cambiar cultivo"
        else:
            condition_note = "sin alerta fuerte en los índices proyectados"
    else:
        condition_note = "sin predicción satelital disponible"

    records = []
    for _, r in cat.iterrows():
        name = r["Nombre_en_AgroRota"]
        family = r["Familia Botánica"]
        perennial = r["Tipo_sistema"] == "frutal_perenne"
        is_current = name == current
        if is_current:
            continue  # el cultivo actual se agrega una sola vez como línea base
        if current_perennial and not is_current:
            # No tratar cultivos anuales como sustitutos de un árbol establecido.
            continue
        if not current_perennial and perennial and current is not None:
            # El catálogo de frutales describe implantaciones perennes; no son una
            # rotación anual equivalente a lechuga/cucurbitáceas/frutilla.
            continue
        if current_family and not is_current and family == current_family:
            continue

        water = _water_score(r["Exigencia de Agua"])
        # Ajuste contextual: poca lluvia reciente/alerta espectral reduce la
        # preferencia por cultivos de alta demanda. No equivale a medir agua de riego.
        water_class = str(r["Exigencia de Agua"]).casefold()
        high_demand = ("alta" in water_class) or ("media-alta" in water_class) or ("media alta" in water_class)
        medium_demand = "media" in water_class
        if dry_context and high_demand:
            water -= 12
        elif dry_context and medium_demand:
            water -= 6
        if stress_signal and high_demand:
            water -= 8
        water = max(0, min(100, water))
        root = _root_score(r["Sistema Radicular"])
        nutrient = _nutrient_score(r["Exigencia de Nutrientes"])
        texture = _soil_texture_score(r["Suelo Recomendado (Textura y pH)"], soil_scenario)
        soil_score = float(np.mean([root, nutrient, texture]))
        temp_score, temp_note = _temperature_fit(latest_temp_30d, r["Temperatura Óptima (°C)"])
        global_score = 0.5 * water + 0.5 * soil_score
        flags = []
        if _is_mo_sensitive(r["Suelo Recomendado (Textura y pH)"]):
            flags.append("La ficha pide suelo rico en MO; MO local no medida")
        if temp_score < 50:
            flags.append(temp_note)
        if family == current_family and current:
            flags.append("misma familia que el cultivo actual")
        if current_perennial:
            flags.append("no reemplazar plantación perenne por cultivo anual")
        if not flags:
            flags.append("validar fecha de siembra y condiciones del lote")
        records.append({
            "tipo_estrategia": "rotacion_de_cultivo",
            "cultivo": name,
            "familia_botanica": family,
            "sistema": r["Tipo_sistema"],
            "prioridad_ahorro_agua_0_100": round(water, 1),
            "proxy_cuidado_suelo_0_100": round(soil_score, 1),
            "compatibilidad_textura_escenario_0_100": texture,
            "compatibilidad_temperatura_0_100": temp_score,
            "puntaje_fijo_50_50": round(global_score, 1),
            "misma_familia_actual": bool(family == current_family and current is not None),
            "requiere_verificar_materia_organica": _is_mo_sensitive(r["Suelo Recomendado (Textura y pH)"]),
            "alertas": "; ".join(flags),
            "contexto_indices": condition_note,
            "contexto_hidrico": "lluvia_30d_baja" if dry_context else "sin_alerta_de_lluvia_30d",
            "escenario_suelo": soil_scenario,
        })

    if current is None:
        records.append({
            "tipo_estrategia": "referencia_pendiente",
            "cultivo": "Actual no especificado",
            "familia_botanica": "desconocida",
            "sistema": "desconocido",
            "prioridad_ahorro_agua_0_100": np.nan,
            "proxy_cuidado_suelo_0_100": np.nan,
            "compatibilidad_textura_escenario_0_100": np.nan,
            "compatibilidad_temperatura_0_100": np.nan,
            "puntaje_fijo_50_50": np.nan,
            "misma_familia_actual": False,
            "requiere_verificar_materia_organica": True,
            "alertas": "Ingresar cultivo actual para aplicar alternancia de familias y comparar contra la situación vigente",
            "contexto_indices": condition_note,
            "contexto_hidrico": "lluvia_30d_baja" if dry_context else "sin_alerta_de_lluvia_30d",
            "escenario_suelo": soil_scenario,
        })
    elif current_row.empty:
        pass
    else:
        r = current_row.iloc[0]
        records.append({
            "tipo_estrategia": "situacion_actual",
            "cultivo": f"ESTRATEGIA ACTUAL: {current}",
            "familia_botanica": r["Familia Botánica"],
            "sistema": r["Tipo_sistema"],
            "prioridad_ahorro_agua_0_100": _water_score(r["Exigencia de Agua"]),
            "proxy_cuidado_suelo_0_100": round(np.mean([
                _root_score(r["Sistema Radicular"]),
                _nutrient_score(r["Exigencia de Nutrientes"]),
                _soil_texture_score(r["Suelo Recomendado (Textura y pH)"], soil_scenario),
            ]), 1),
            "compatibilidad_textura_escenario_0_100": _soil_texture_score(r["Suelo Recomendado (Textura y pH)"], soil_scenario),
            "compatibilidad_temperatura_0_100": _temperature_fit(latest_temp_30d, r["Temperatura Óptima (°C)"])[0],
            "puntaje_fijo_50_50": round(0.5 * _water_score(r["Exigencia de Agua"]) + 0.5 * np.mean([
                _root_score(r["Sistema Radicular"]), _nutrient_score(r["Exigencia de Nutrientes"]),
                _soil_texture_score(r["Suelo Recomendado (Textura y pH)"], soil_scenario)
            ]), 1),
            "misma_familia_actual": True,
            "requiere_verificar_materia_organica": _is_mo_sensitive(r["Suelo Recomendado (Textura y pH)"]),
            "alertas": "Estrategia de referencia; si es anual, repetir la misma familia eleva el riesgo de rotación",
            "contexto_indices": condition_note,
            "contexto_hidrico": "lluvia_30d_baja" if dry_context else "sin_alerta_de_lluvia_30d",
            "escenario_suelo": soil_scenario,
        })
        if current_perennial:
            # Una plantación arbórea establecida no se reemplaza como si fuera un
            # cultivo anual. Se muestran prácticas de manejo complementario sin
            # inventar cultivos, Kc ni puntuaciones que el catálogo no respalda.
            management_rows = [
                (
                    "MANTENER ARBOLADO + COBERTURA VIVA EN INTERLÍNEAS",
                    "Evaluar una cubierta de bajo consumo, adaptada a la zona, sin competir con el frutal; especie y fecha requieren validación local.",
                ),
                (
                    "MANTENER ARBOLADO + ACOLCHADO / RESIDUOS VEGETALES",
                    "Conservar residuos vegetales limpios como cobertura del suelo; ajustar espesor y manejo para evitar problemas sanitarios o de humedad.",
                ),
            ]
            for strategy, note in management_rows:
                records.append({
                    "tipo_estrategia": "manejo_complementario_perenne",
                    "cultivo": strategy,
                    "familia_botanica": "no aplica",
                    "sistema": "manejo de plantación perenne",
                    "prioridad_ahorro_agua_0_100": np.nan,
                    "proxy_cuidado_suelo_0_100": np.nan,
                    "compatibilidad_textura_escenario_0_100": np.nan,
                    "compatibilidad_temperatura_0_100": np.nan,
                    "puntaje_fijo_50_50": np.nan,
                    "misma_familia_actual": False,
                    "requiere_verificar_materia_organica": True,
                    "alertas": note + " No es una rotación anual ni tiene puntaje comparable.",
                    "contexto_indices": condition_note,
                    "contexto_hidrico": "verificar_humedad_y_competencia_con_frutal",
                    "escenario_suelo": soil_scenario,
                })

    result = pd.DataFrame(records)
    current_mask = result["cultivo"].str.startswith("ESTRATEGIA ACTUAL") | result["cultivo"].eq("Actual no especificado")
    result = pd.concat([
        result[current_mask],
        result[~current_mask].sort_values("puntaje_fijo_50_50", ascending=False)
    ], ignore_index=True)
    result.insert(0, "orden", range(1, len(result) + 1))
    return result
