"""Integracion robusta de Sentinel-2 y NASA POWER para AgroRota.

Contrato principal:
    generar_dataset_agricola(ruta_sentinel, ruta_weather, ruta_salida)

Se conserva una fila por cada mosaico diario Sentinel. Las observaciones
climaticas se agregan con ventanas retrospectivas que incluyen la fecha de
la observacion. Una ventana incompleta queda como NaN en sus estadisticos,
pero su fila satelital nunca se elimina.
"""

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


COLUMNAS_CLIMA = {
    "precipitacion_mm_dia": "precipitacion",
    "temperatura_media_c": "temperatura_media",
    "temperatura_maxima_c": "temperatura_maxima",
    "temperatura_minima_c": "temperatura_minima",
}


def _normalizar_fecha(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    if "fecha" not in df.columns:
        raise ValueError(f"El archivo {nombre} no contiene la columna 'fecha'.")
    salida = df.copy()
    salida["fecha"] = pd.to_datetime(salida["fecha"], errors="coerce")
    invalidas = int(salida["fecha"].isna().sum())
    if invalidas:
        raise ValueError(
            f"El archivo {nombre} contiene {invalidas} fechas invalidas. "
            "Corregilas antes de integrar para no perder observaciones."
        )
    # Fechas diarias: se normalizan a medianoche.
    if getattr(salida["fecha"].dt, "tz", None) is not None:
        salida["fecha"] = salida["fecha"].dt.tz_localize(None)
    salida["fecha"] = salida["fecha"].dt.normalize()
    return salida


def _convertir_numericas(df: pd.DataFrame, columnas: Iterable[str]) -> pd.DataFrame:
    salida = df.copy()
    for columna in columnas:
        if columna not in salida.columns:
            raise ValueError(
                f"Falta la columna meteorologica '{columna}'. "
                "Verifica los nombres producidos por src/weather.py."
            )
        salida[columna] = pd.to_numeric(salida[columna], errors="coerce")
        salida[columna] = salida[columna].replace(
            [-999, -999.0, -9999, -9999.0, np.inf, -np.inf], np.nan
        )
    return salida


def cargar_datasets(ruta_sentinel: str, ruta_weather: str):
    """Carga y valida los CSV satelital y meteorologico."""
    ruta_sentinel = Path(ruta_sentinel)
    ruta_weather = Path(ruta_weather)
    if not ruta_sentinel.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_sentinel}")
    if not ruta_weather.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta_weather}")

    sat = pd.read_csv(ruta_sentinel)
    met = pd.read_csv(ruta_weather)
    if sat.empty:
        raise ValueError("El archivo Sentinel-2 esta vacio.")
    if met.empty:
        raise ValueError("El archivo meteorologico esta vacio.")

    sat = _normalizar_fecha(sat, str(ruta_sentinel))
    met = _normalizar_fecha(met, str(ruta_weather))

    if sat["fecha"].duplicated().any():
        ejemplos = sat.loc[sat["fecha"].duplicated(False), "fecha"].dt.strftime("%Y-%m-%d").tolist()[:10]
        raise ValueError(
            "Sentinel-2 debe tener una sola fila por mosaico diario. "
            f"Fechas duplicadas (muestra): {ejemplos}"
        )
    if met["fecha"].duplicated().any():
        ejemplos = met.loc[met["fecha"].duplicated(False), "fecha"].dt.strftime("%Y-%m-%d").tolist()[:10]
        raise ValueError(
            "NASA POWER debe tener una fila por dia. "
            f"Fechas duplicadas (muestra): {ejemplos}"
        )

    met = _convertir_numericas(met, COLUMNAS_CLIMA.keys())
    sat = sat.sort_values("fecha").reset_index(drop=True)
    met = met.sort_values("fecha").reset_index(drop=True)
    return sat, met


def calcular_indicadores_climaticos(df_weather: pd.DataFrame) -> pd.DataFrame:
    """Calcula ventanas retrospectivas 7/30 dias sin descartar fechas.

    Los acumulados/promedios se publican solo cuando hay todos los dias
    esperados con dato valido. Los conteos siempre se conservan para poder
    auditar la cobertura de cada ventana.
    """
    met = _normalizar_fecha(df_weather, "dataset meteorologico")
    met = _convertir_numericas(met, COLUMNAS_CLIMA.keys())
    if met["fecha"].duplicated().any():
        raise ValueError("Hay fechas duplicadas en el dataset meteorologico.")

    met = met.set_index("fecha").sort_index()
    # Reindexar a calendario diario permite contar huecos reales, no solo filas.
    calendario = pd.date_range(met.index.min(), met.index.max(), freq="D")
    met = met.reindex(calendario)
    met.index.name = "fecha"

    salida = pd.DataFrame(index=met.index)
    for dias in (7, 30):
        ventana = met.rolling(window=dias, min_periods=1)

        # Precipitacion: suma solo interpretable como acumulado de la ventana
        # cuando todos los dias tienen dato; el conteo queda disponible siempre.
        lluvia = met["precipitacion_mm_dia"]
        conteo_lluvia = lluvia.rolling(dias, min_periods=1).count()
        suma_lluvia = lluvia.rolling(dias, min_periods=1).sum()
        salida[f"dias_con_datos_precipitacion_{dias}d"] = conteo_lluvia.astype("Int64")
        salida[f"precipitacion_acumulada_{dias}d_mm"] = suma_lluvia.where(conteo_lluvia.eq(dias))

        # Temperaturas: promedio/max/min solo si la ventana esta completa.
        for columna, prefijo, operacion in (
            ("temperatura_media_c", "temperatura_media", "mean"),
            ("temperatura_maxima_c", "temperatura_maxima", "mean"),
            ("temperatura_minima_c", "temperatura_minima", "mean"),
        ):
            serie = met[columna]
            conteo = serie.rolling(dias, min_periods=1).count()
            agregado = getattr(serie.rolling(dias, min_periods=1), operacion)()
            salida[f"{prefijo}_{dias}d_c"] = agregado.where(conteo.eq(dias))
            salida[f"dias_con_datos_{prefijo}_{dias}d"] = conteo.astype("Int64")

    salida = salida.reset_index()
    return salida


def integrar_datasets(df_sentinel: pd.DataFrame, df_weather: pd.DataFrame) -> pd.DataFrame:
    """Une clima a Sentinel con LEFT JOIN: nunca descarta mosaicos."""
    sat = _normalizar_fecha(df_sentinel, "dataset Sentinel-2")
    met = _normalizar_fecha(df_weather, "dataset meteorologico")

    if sat["fecha"].duplicated().any():
        raise ValueError("El dataset Sentinel contiene fechas duplicadas.")

    clima = calcular_indicadores_climaticos(met)
    if clima["fecha"].duplicated().any():
        raise ValueError("Los indicadores climaticos contienen fechas duplicadas.")

    resultado = sat.merge(
        clima,
        on="fecha",
        how="left",
        validate="one_to_one",
        indicator="_estado_integracion",
    )

    no_encontradas = int(resultado["_estado_integracion"].eq("left_only").sum())
    resultado = resultado.drop(columns="_estado_integracion")
    resultado = resultado.sort_values("fecha").reset_index(drop=True)

    if len(resultado) != len(sat):
        raise RuntimeError(
            "La integracion altero la cantidad de observaciones Sentinel: "
            f"entrada={len(sat)}, salida={len(resultado)}."
        )

    print("\nDetalle de integracion LEFT JOIN")
    print("Observaciones Sentinel de entrada:", len(sat))
    print("Observaciones agricolas de salida:", len(resultado))
    print("Fechas sin correspondencia meteorologica:", no_encontradas)
    print("Filas satelitales conservadas:", len(resultado))
    return resultado


def guardar_dataset(df: pd.DataFrame, ruta_salida: str) -> None:
    ruta = Path(ruta_salida)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    print("Dataset agricola guardado correctamente.")
    print("Ruta:", ruta.resolve())


def preparar_datasets(ruta_sentinel: str, ruta_weather: str):
    """Carga, valida y devuelve el dataset integrado."""
    sat, met = cargar_datasets(ruta_sentinel, ruta_weather)
    return integrar_datasets(sat, met)


def generar_dataset_agricola(
    ruta_sentinel: str,
    ruta_weather: str,
    ruta_salida: str,
) -> pd.DataFrame:
    """Funcion de entrada usada por basededatos.py."""
    print("\n===================================")
    print("INTEGRACION DE DATOS AGRICOLAS")
    print("===================================")

    sat, met = cargar_datasets(ruta_sentinel, ruta_weather)
    print("Observaciones Sentinel:", len(sat))
    print("Observaciones meteorologicas:", len(met))

    resultado = integrar_datasets(sat, met)
    guardar_dataset(resultado, ruta_salida)

    print("Observaciones:", len(resultado))
    print("Variables:", len(resultado.columns))
    print("\nPrimeras filas:")
    print(resultado.head().to_string(index=False))
    return resultado
