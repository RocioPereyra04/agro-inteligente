
# src/weather.py

import requests
import pandas as pd
import numpy as np

from pathlib import Path
from datetime import datetime


# ==========================================
# CONFIGURACIÓN NASA POWER
# ==========================================

NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)

PARAMETROS = [
    "PRECTOTCORR",
    "T2M",
    "T2M_MAX",
    "T2M_MIN"
]

NOMBRES_COLUMNAS = {
    "PRECTOTCORR": "precipitacion_mm_dia",
    "T2M": "temperatura_media_c",
    "T2M_MAX": "temperatura_maxima_c",
    "T2M_MIN": "temperatura_minima_c"
}


# ==========================================
# 1. CONSULTAR NASA POWER
# ==========================================

def consultar_nasa_power(
    latitud,
    longitud,
    fecha_inicio,
    fecha_fin
):
    """
    Consulta datos meteorológicos diarios de NASA POWER.
    """

    # Validar coordenadas
    if not -90 <= latitud <= 90:
        raise ValueError("Latitud fuera de rango.")

    if not -180 <= longitud <= 180:
        raise ValueError("Longitud fuera de rango.")

    # Validar fechas
    try:
        inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Las fechas deben tener formato YYYY-MM-DD.")

    if inicio > fin:
        raise ValueError(
            "La fecha inicial no puede ser posterior a la final."
        )

    parametros = {
        "parameters": ",".join(PARAMETROS),
        "community": "AG",
        "longitude": longitud,
        "latitude": latitud,
        "start": inicio.strftime("%Y%m%d"),
        "end": fin.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC"
    }

    print("\nConsultando NASA POWER...")

    try:
        respuesta = requests.get(
            NASA_POWER_URL,
            params=parametros,
            timeout=60
        )

        respuesta.raise_for_status()

        datos = respuesta.json()

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "NASA POWER tardó demasiado en responder."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"Error de conexión con NASA POWER: {error}"
        )

    except ValueError:
        raise RuntimeError(
            "NASA POWER devolvió una respuesta JSON inválida."
        )

    # Verificar respuesta
    if "properties" not in datos:
        raise ValueError(
            f"Respuesta inesperada de NASA POWER: {datos}"
        )

    if "parameter" not in datos["properties"]:
        raise ValueError(
            "No se encontraron parámetros meteorológicos."
        )

    datos_meteorologicos = datos["properties"]["parameter"]

    return datos_meteorologicos


# ==========================================
# 2. CONVERTIR JSON A DATAFRAME
# ==========================================

def convertir_a_dataframe(datos):

    fechas = sorted(datos[PARAMETROS[0]].keys())

    df = pd.DataFrame({
        parametro: [
            datos[parametro].get(fecha, np.nan)
            for fecha in fechas
        ]
        for parametro in PARAMETROS
    })

    df.insert(
        0,
        "fecha",
        pd.to_datetime(fechas, format="%Y%m%d")
    )

    df = df.replace([-999, -999.0, np.inf, -np.inf], np.nan)

    df = df.rename(columns=NOMBRES_COLUMNAS)

    return df.sort_values("fecha").reset_index(drop=True)

# ==========================================
# 3. DESCARGAR DATASET METEOROLÓGICO
# ==========================================

def obtener_dataset_meteorologico(
    latitud,
    longitud,
    fecha_inicio,
    fecha_fin,
    salida_csv="data/processed/weather_parcela.csv"
):
    """
    Descarga datos meteorológicos desde NASA POWER,
    los procesa y guarda un CSV.
    """

    print("\n================================")
    print("PROCESAMIENTO METEOROLÓGICO")
    print("================================")

    print(f"Latitud: {latitud}")
    print(f"Longitud: {longitud}")
    print(f"Desde: {fecha_inicio}")
    print(f"Hasta: {fecha_fin}")

    # Consultar API
    datos = consultar_nasa_power(
        latitud=latitud,
        longitud=longitud,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin
    )

    # Convertir a DataFrame
    df = convertir_a_dataframe(datos)

    if df.empty:
        raise ValueError(
            "NASA POWER no devolvió observaciones."
        )

    # Crear directorio
    ruta = Path(salida_csv)

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Guardar CSV
    df.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nDescarga finalizada.")
    print(f"Registros obtenidos: {len(df)}")
    print(f"Archivo guardado en: {ruta}")

    print("\nPrimeras observaciones:")
    print(df.head())

    return df
