"""Evaluación multicriterio explicable para AgroRota.

No entrena modelos ni inventa puntuaciones. Solo compara alternativas cuando
la viabilidad agronómica está validada y existen puntuaciones 0-100 para todos
los criterios priorizados por el productor.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
CARPETA_AGRONOMIA = BASE_DIR / "data" / "processed" / "agronomy"
CARPETA_PREFERENCIAS = BASE_DIR / "data" / "processed" / "preferences"

ARCHIVO_ALTERNATIVAS = CARPETA_AGRONOMIA / "alternativas_campana.csv"
ARCHIVO_PREFERENCIAS = CARPETA_PREFERENCIAS / "preferencias_campana.csv"
ARCHIVO_SALIDA = BASE_DIR / "data" / "processed" / "resultado_multicriterio.csv"

MAPEO_CRITERIOS = {
    "ahorrar_agua": "score_agua",
    "mejorar_suelo": "score_suelo",
    "aumentar_ingresos": "score_ingresos",
    "invertir_poco": "score_inversion",
    "cosechar_pronto": "score_tiempo",
    "reducir_riesgo": "score_riesgo",
    "vender_facil": "score_mercado",
    "autoconsumo": "score_autoconsumo",
}


def _normalizar_si_no(valor: object) -> str:
    if pd.isna(valor) or str(valor).strip() == "":
        return "NO_EVALUADA"
    valor = str(valor).strip().upper()
    equivalencias = {
        "SI": "SI", "SÍ": "SI", "YES": "SI", "TRUE": "SI", "1": "SI",
        "NO": "NO", "FALSE": "NO", "0": "NO",
        "NO_EVALUADA": "NO_EVALUADA", "PENDIENTE": "NO_EVALUADA",
    }
    return equivalencias.get(valor, "NO_EVALUADA")


def cargar_preferencias(ruta: Path) -> Dict[str, float]:
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo de preferencias: {ruta}")

    df = pd.read_csv(ruta, encoding="utf-8-sig")
    requeridas = {"prioridad", "peso", "activa"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en preferencias_campana.csv: {sorted(faltantes)}")

    if df.empty:
        raise ValueError(
            "No hay prioridades cargadas. El productor debe elegir una o más "
            "prioridades antes de comparar alternativas."
        )

    activas = df[df["activa"].astype(str).str.strip().str.lower().isin(
        ["1", "true", "si", "sí", "x", "s"]
    )].copy()

    if activas.empty:
        raise ValueError("No hay prioridades activas en preferencias_campana.csv.")

    pesos: Dict[str, float] = {}
    for _, fila in activas.iterrows():
        prioridad = str(fila["prioridad"]).strip()
        if prioridad not in MAPEO_CRITERIOS:
            raise ValueError(f"Prioridad desconocida: {prioridad}")
        peso = pd.to_numeric(fila["peso"], errors="coerce")
        if pd.isna(peso) or not 1 <= float(peso) <= 3:
            raise ValueError(
                f"El peso de '{prioridad}' debe ser un número entre 1 y 3."
            )
        if prioridad in pesos:
            raise ValueError(f"La prioridad '{prioridad}' está repetida.")
        pesos[prioridad] = float(peso)

    return pesos


def evaluar_alternativas(
    alternativas: pd.DataFrame,
    pesos: Dict[str, float],
) -> pd.DataFrame:
    if alternativas.empty:
        raise ValueError("No hay alternativas cargadas para comparar.")
    if not pesos:
        raise ValueError("No se recibieron prioridades activas.")

    requeridas = {"alternativa_id", "cultivo_id", "viabilidad_agronomica"}
    faltantes_columnas = requeridas - set(alternativas.columns)
    if faltantes_columnas:
        raise ValueError(
            f"Faltan columnas en alternativas_campana.csv: {sorted(faltantes_columnas)}"
        )

    criterios_activos = [MAPEO_CRITERIOS[p] for p in pesos]
    columnas_faltantes = [c for c in criterios_activos if c not in alternativas.columns]
    if columnas_faltantes:
        raise ValueError(f"Faltan columnas de puntuación: {columnas_faltantes}")

    total_pesos = sum(pesos.values())
    filas: List[dict] = []

    for _, fila in alternativas.iterrows():
        alternativa_id = str(fila.get("alternativa_id", "")).strip()
        cultivo_id = str(fila.get("cultivo_id", "")).strip()
        viabilidad = _normalizar_si_no(fila.get("viabilidad_agronomica"))

        resultado = {
            "alternativa_id": alternativa_id,
            "cultivo_id": cultivo_id,
            "viabilidad_agronomica": viabilidad,
            "puntaje_mcdm": pd.NA,
            "orden": pd.NA,
            "estado_evaluacion": "",
            "criterios_usados": ";".join(pesos.keys()),
            "criterios_faltantes": "",
            "observaciones": "",
        }

        if not alternativa_id or not cultivo_id:
            resultado["estado_evaluacion"] = "REGISTRO_INCOMPLETO"
            resultado["observaciones"] = "Falta alternativa_id o cultivo_id."
            filas.append(resultado)
            continue

        if viabilidad == "NO":
            resultado["estado_evaluacion"] = "DESCARTADA_POR_VIABILIDAD"
            resultado["observaciones"] = (
                "La alternativa fue marcada como no viable antes del puntaje."
            )
            filas.append(resultado)
            continue

        if viabilidad != "SI":
            resultado["estado_evaluacion"] = "FALTA_VALIDAR_VIABILIDAD"
            resultado["observaciones"] = (
                "No se puntúa hasta validar suelo, agua, calendario y sanidad."
            )
            filas.append(resultado)
            continue

        valores = {}
        criterios_faltantes = []
        for prioridad, columna in ((p, MAPEO_CRITERIOS[p]) for p in pesos):
            valor = pd.to_numeric(pd.Series([fila.get(columna)]), errors="coerce").iloc[0]
            if pd.isna(valor):
                criterios_faltantes.append(prioridad)
            elif not 0 <= float(valor) <= 100:
                raise ValueError(
                    f"Puntuación fuera de rango [0,100] en {alternativa_id}: {columna}={valor}"
                )
            else:
                valores[prioridad] = float(valor)

        if criterios_faltantes:
            resultado["estado_evaluacion"] = "DATOS_INSUFICIENTES"
            resultado["criterios_faltantes"] = ";".join(criterios_faltantes)
            resultado["observaciones"] = (
                "No se calcula un puntaje parcial para evitar favorecer "
                "alternativas con información incompleta."
            )
            filas.append(resultado)
            continue

        puntaje = sum(valores[p] * pesos[p] for p in pesos) / total_pesos
        resultado["puntaje_mcdm"] = round(puntaje, 2)
        resultado["estado_evaluacion"] = "EVALUADA"
        resultado["observaciones"] = (
            "Puntaje comparable; revisar fuentes y restricciones antes de decidir."
        )
        filas.append(resultado)

    salida = pd.DataFrame(filas)
    mascara = salida["estado_evaluacion"].eq("EVALUADA")
    evaluadas = salida.loc[mascara].sort_values(
        "puntaje_mcdm", ascending=False, kind="stable"
    )
    for orden, idx in enumerate(evaluadas.index, start=1):
        salida.loc[idx, "orden"] = orden

    if evaluadas.empty:
        estado_general = "SIN_RECOMENDACION_POR_DATOS_INSUFICIENTES"
    elif (salida["estado_evaluacion"] != "EVALUADA").any():
        estado_general = "COMPARACION_PARCIAL"
    else:
        estado_general = "COMPARACION_COMPLETA"

    salida.insert(0, "estado_general", estado_general)
    return salida


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calcula una comparación multicriterio explicable, sin ML."
    )
    parser.add_argument("--alternativas", type=Path, default=ARCHIVO_ALTERNATIVAS)
    parser.add_argument("--preferencias", type=Path, default=ARCHIVO_PREFERENCIAS)
    parser.add_argument("--salida", type=Path, default=ARCHIVO_SALIDA)
    args = parser.parse_args()

    alternativas = pd.read_csv(args.alternativas, encoding="utf-8-sig")
    pesos = cargar_preferencias(args.preferencias)
    resultado = evaluar_alternativas(alternativas, pesos)

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(args.salida, index=False, encoding="utf-8-sig")

    print("\nEVALUACIÓN MULTICRITERIO")
    print("Prioridades y pesos:", pesos)
    print(resultado.to_string(index=False))
    print("\nArchivo guardado en:", args.salida.resolve())
    print("No se entrenó ningún modelo de Machine Learning.")


if __name__ == "__main__":
    main()
