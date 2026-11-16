from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.satellite import (
    inicializar_gee,
    crear_parcela,
    obtener_dataset_satelital,
)
from src.weather import obtener_dataset_meteorologico
from src.preprocessing import generar_dataset_agricola


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

PROJECT_ID = "base-de-datos-514723"

COORDENADAS = [
    [-65.92953525054749, -32.36413966044574],
    [-65.928853303228, -32.3649093364855],
    [-65.92861002882191, -32.36421895878116],
    [-65.92875716613071, -32.36396344473609],
    [-65.92953525054749, -32.36413966044574],
]

LATITUD = -32.364307
LONGITUD = -65.928939

ANIOS_HISTORICOS = 10  # Período móvil de los últimos diez años
MAX_NUBOSIDAD = 80
ESCALA_SATELITAL = 20

RUTA_SENTINEL = DATA_DIR / "processed/indices_parcela.csv"
RUTA_WEATHER = DATA_DIR / "processed/weather_parcela.csv"
RUTA_AGRICOLA = DATA_DIR / "processed/dataset_agricola.csv"


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def crear_directorios():
    """Crea los directorios de datos si todavía no existen."""
    directorios = [
        DATA_DIR / "raw/sentinel",
        DATA_DIR / "raw/weather",
        DATA_DIR / "processed",
        DATA_DIR / "processed/eda",
        DATA_DIR / "processed/agronomy",
        DATA_DIR / "processed/preferences",
    ]

    for directorio in directorios:
        directorio.mkdir(parents=True, exist_ok=True)


def imprimir_titulo(titulo):
    """Imprime un encabezado para ordenar la salida de consola."""
    print("\n" + "=" * 60)
    print(f" {titulo}")
    print("=" * 60)


def validar_columnas(df, columnas, nombre_dataset):
    """Comprueba que un DataFrame contenga las columnas requeridas."""
    faltantes = [col for col in columnas if col not in df.columns]

    if faltantes:
        raise ValueError(
            f"Faltan columnas en {nombre_dataset}: {faltantes}"
        )


def cargar_y_validar_fechas(ruta, nombre_dataset):
    """Carga un CSV y convierte su columna fecha a datetime."""
    df = pd.read_csv(ruta)

    if df.empty:
        raise ValueError(f"El dataset {nombre_dataset} está vacío.")

    validar_columnas(df, ["fecha"], nombre_dataset)

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    fechas_invalidas = df["fecha"].isna().sum()

    if fechas_invalidas:
        print(
            f"ADVERTENCIA: {fechas_invalidas} filas de "
            f"{nombre_dataset} tienen fechas inválidas y serán descartadas."
        )
        df = df.dropna(subset=["fecha"]).copy()

    if df.empty:
        raise ValueError(
            f"No quedaron registros con fechas válidas en {nombre_dataset}."
        )

    # Normalizar a medianoche para comparar fechas diarias.
    df["fecha"] = df["fecha"].dt.normalize()

    return df


def controlar_fechas_sentinel(df_sentinel):
    """Verifica que Sentinel ya contenga una fila por mosaico diario."""
    imprimir_titulo("CONTROL DE MOSAICOS DIARIOS")

    validar_columnas(
        df_sentinel,
        ["fecha", "imagen_id", "escenas_mosaico"],
        "dataset Sentinel-2",
    )

    duplicados = df_sentinel.duplicated(subset=["fecha"]).sum()

    print("Observaciones satelitales:", len(df_sentinel))
    print("Fechas duplicadas:", duplicados)

    if duplicados:
        raise ValueError(
            "Se encontraron fechas duplicadas en Sentinel-2. "
            "Revisá la generación de mosaicos diarios en src/satellite.py."
        )

    print("\nCantidad de escenas por mosaico:")
    print(df_sentinel["escenas_mosaico"].describe())

    print("\nPrimeros mosaicos:")
    print(
        df_sentinel[
            ["fecha", "imagen_id", "escenas_mosaico"]
        ].head(10).to_string(index=False)
    )


def controlar_fechas_weather(
    df_weather,
    fecha_inicio_weather,
    fecha_fin_weather,
):
    """Verifica duplicados y continuidad de fechas meteorológicas."""
    imprimir_titulo("CONTROL DE DATOS METEOROLÓGICOS")

    duplicados = df_weather.duplicated(subset=["fecha"]).sum()
    print("Registros meteorológicos:", len(df_weather))
    print("Fechas meteorológicas duplicadas:", duplicados)

    if duplicados:
        raise ValueError(
            "Existen fechas meteorológicas duplicadas en weather_parcela.csv."
        )

    fechas_esperadas = pd.date_range(
        start=fecha_inicio_weather,
        end=fecha_fin_weather,
        freq="D",
    )

    fechas_disponibles = pd.DatetimeIndex(
        df_weather["fecha"].drop_duplicates().sort_values()
    )

    fechas_faltantes = fechas_esperadas.difference(fechas_disponibles)

    print("Días meteorológicos esperados:", len(fechas_esperadas))
    print("Días meteorológicos obtenidos:", len(fechas_disponibles))
    print("Días meteorológicos faltantes:", len(fechas_faltantes))

    if len(fechas_faltantes):
        print("Fechas faltantes:")
        print(fechas_faltantes.strftime("%Y-%m-%d").tolist())
        print(
            "ADVERTENCIA: revisá la cobertura. Las ventanas de 7 y 30 días "
            "deben reflejar los días realmente disponibles."
        )
    else:
        print("Cobertura diaria del período: completa.")


def comparar_fechas_sentinel_agricola(df_sentinel, df_agricola):
    """Detecta observaciones satelitales perdidas durante la integración."""
    fechas_sentinel = set(pd.to_datetime(df_sentinel["fecha"]).dt.normalize())
    fechas_agricola = set(pd.to_datetime(df_agricola["fecha"]).dt.normalize())
    faltan = sorted(fechas_sentinel - fechas_agricola)
    sobran = sorted(fechas_agricola - fechas_sentinel)

    print("\nCONTROL DE CONSERVACIÓN DE OBSERVACIONES")
    print("Fechas Sentinel:", len(fechas_sentinel))
    print("Fechas dataset agrícola:", len(fechas_agricola))
    print("Fechas Sentinel no integradas:", len(faltan))
    print("Fechas adicionales en integración:", len(sobran))

    if faltan:
        print("Fechas Sentinel que se perdieron:")
        print([f.strftime("%Y-%m-%d") for f in faltan])
    if sobran:
        print("Fechas que no estaban en Sentinel:")
        print([f.strftime("%Y-%m-%d") for f in sobran])

    if faltan or sobran:
        raise ValueError(
            "La integración no conservó exactamente las fechas Sentinel. "
            "Revisá src/preprocessing.py y la generación del dataset agrícola."
        )


def controlar_dataset_agricola(df):
    """Ejecuta controles de calidad sobre el dataset integrado."""
    imprimir_titulo("CONTROL DE CALIDAD DEL DATASET AGRÍCOLA")

    validar_columnas(
        df,
        [
            "fecha",
            "NDVI_mean",
            "MSI_mean",
            "NDVI_count",
            "MSI_count",
            "dias_con_datos_precipitacion_7d",
            "dias_con_datos_precipitacion_30d",
        ],
        "dataset agrícola",
    )

    print("\nCantidad de observaciones:", len(df))
    print("Cantidad de variables:", len(df.columns))
    print("Desde:", df["fecha"].min().date())
    print("Hasta:", df["fecha"].max().date())

    duplicados = df.duplicated(subset=["fecha"]).sum()
    print("\nFechas duplicadas:", duplicados)

    if duplicados:
        raise ValueError(
            "El dataset agrícola contiene fechas duplicadas."
        )

    # Cobertura meteorológica retrospectiva.
    columnas_cobertura = [
        "dias_con_datos_precipitacion_7d",
        "dias_con_datos_precipitacion_30d",
    ]

    print("\nCobertura meteorológica:")
    for columna in columnas_cobertura:
        print(f"\n{columna}:")
        print(df[columna].describe())

    # Índices espectrales.
    print("\nEstadísticas NDVI:")
    print(df["NDVI_mean"].describe())

    ndvi_fuera_rango = (
        (df["NDVI_mean"] < -1) | (df["NDVI_mean"] > 1)
    ).sum()

    if ndvi_fuera_rango:
        print(
            f"ADVERTENCIA: {ndvi_fuera_rango} valores NDVI_mean "
            "están fuera del rango [-1, 1]."
        )
    else:
        print("NDVI_mean dentro del rango esperado [-1, 1].")

    print("\nEstadísticas MSI:")
    print(df["MSI_mean"].describe())

    msi_negativo = (df["MSI_mean"] < 0).sum()
    if msi_negativo:
        print(
            f"ADVERTENCIA: {msi_negativo} valores MSI_mean son negativos."
        )
    else:
        print("MSI_mean no presenta valores negativos.")

    # Cantidad de píxeles válidos.
    print("\nCantidad de píxeles válidos:")
    for columna in ["NDVI_count", "MSI_count"]:
        print(f"\n{columna}:")
        print(df[columna].describe())

        pocos_pixeles = (df[columna] < 5).sum()
        if pocos_pixeles:
            print(
                f"ADVERTENCIA: {pocos_pixeles} observaciones tienen "
                f"menos de 5 píxeles válidos en {columna}."
            )

    # Escenas incluidas en cada mosaico, si la columna se conservó
    # durante la integración.
    if "escenas_mosaico" in df.columns:
        print("\nEscenas por mosaico:")
        print(df["escenas_mosaico"].describe())
    else:
        print(
            "\nAVISO: la columna escenas_mosaico no está en el dataset "
            "integrado. Se puede consultar en indices_parcela.csv."
        )

    # Intervalos entre adquisiciones.
    df_ordenado = df.sort_values("fecha").reset_index(drop=True)
    intervalos = df_ordenado["fecha"].diff().dt.days.dropna()

    print("\nIntervalos entre observaciones (días):")
    if not intervalos.empty:
        print(intervalos.describe())
    else:
        print("No hay suficientes observaciones para calcular intervalos.")

    # Valores faltantes.
    print("\nValores faltantes por columna:")
    print(df.isna().sum())

    print("\nPorcentaje de valores faltantes:")
    print((df.isna().mean() * 100).round(2).sort_values(ascending=False))

    print("\nInformación general:")
    df.info()

    print("\nEstadísticas descriptivas:")
    print(df.describe())


# ============================================================
# PROCESO PRINCIPAL
# ============================================================

def main():
    imprimir_titulo("SISTEMA DE ANÁLISIS AGRÍCOLA")

    crear_directorios()

    # --------------------------------------------------------
    # 1. Definir período de análisis
    # --------------------------------------------------------
    hoy = pd.Timestamp(date.today()).normalize()

    fecha_inicio_sentinel = (
        hoy - pd.DateOffset(years=ANIOS_HISTORICOS)
    ).date()

    # Earth Engine interpreta filterDate(fecha_inicio, fecha_fin)
    # con fecha_fin exclusiva. Por eso se suma un día.
    fecha_fin_sentinel = (
        hoy + pd.Timedelta(days=1)
    ).date()

    print("\nPeríodo de análisis:")
    print(f"Antigüedad solicitada: {ANIOS_HISTORICOS} años")
    print("Desde:", fecha_inicio_sentinel)
    print("Hasta:", fecha_fin_sentinel - timedelta(days=1))
    print("Nota: la disponibilidad real de Sentinel-2 puede comenzar después")
    print("de la fecha inicial solicitada, según el archivo de la colección.")

    # --------------------------------------------------------
    # 2. Obtener datos Sentinel-2 y generar mosaicos diarios
    # --------------------------------------------------------
    imprimir_titulo("PROCESAMIENTO SATELITAL")

    inicializar_gee(PROJECT_ID)
    parcela = crear_parcela(COORDENADAS)

    obtener_dataset_satelital(
        parcela=parcela,
        fecha_inicio=fecha_inicio_sentinel.strftime("%Y-%m-%d"),
        fecha_fin=fecha_fin_sentinel.strftime("%Y-%m-%d"),
        salida_csv=str(RUTA_SENTINEL),
        max_nubosidad=MAX_NUBOSIDAD,
        escala=ESCALA_SATELITAL,
    )

    df_sentinel = cargar_y_validar_fechas(
        RUTA_SENTINEL,
        "dataset Sentinel-2",
    )

    controlar_fechas_sentinel(df_sentinel)

    # --------------------------------------------------------
    # 3. Determinar período meteorológico
    # --------------------------------------------------------
    imprimir_titulo("PERÍODO METEOROLÓGICO")

    primera_fecha = df_sentinel["fecha"].min()
    ultima_fecha = df_sentinel["fecha"].max()

    # Para una ventana retrospectiva de 30 días que incluya
    # la fecha de observación, se requieren 29 días anteriores.
    fecha_inicio_weather = (
        primera_fecha - pd.Timedelta(days=29)
    ).date()

    # La fecha final de NASA POWER se solicita de forma inclusiva.
    fecha_fin_weather = ultima_fecha.date()

    print("Primera observación satelital:", primera_fecha.date())
    print("Última observación satelital:", ultima_fecha.date())
    print("Inicio meteorológico:", fecha_inicio_weather)
    print("Fin meteorológico:", fecha_fin_weather)

    # --------------------------------------------------------
    # 4. Obtener datos meteorológicos NASA POWER
    # --------------------------------------------------------
    imprimir_titulo("PROCESAMIENTO METEOROLÓGICO")

    df_weather = obtener_dataset_meteorologico(
        latitud=LATITUD,
        longitud=LONGITUD,
        fecha_inicio=fecha_inicio_weather.strftime("%Y-%m-%d"),
        fecha_fin=fecha_fin_weather.strftime("%Y-%m-%d"),
        salida_csv=str(RUTA_WEATHER),
    )

    if df_weather is None or df_weather.empty:
        raise ValueError("No se obtuvieron datos meteorológicos.")

    # Se vuelve a cargar desde el CSV para aplicar exactamente
    # los mismos controles sobre el archivo que utilizará el pipeline.
    df_weather = cargar_y_validar_fechas(
        RUTA_WEATHER,
        "dataset meteorológico",
    )

    controlar_fechas_weather(
        df_weather,
        fecha_inicio_weather,
        fecha_fin_weather,
    )

    # --------------------------------------------------------
    # 5. Integrar Sentinel-2 y meteorología
    # --------------------------------------------------------
    imprimir_titulo("INTEGRACIÓN DE DATOS AGRÍCOLAS")

    df_agricola = generar_dataset_agricola(
        ruta_sentinel=str(RUTA_SENTINEL),
        ruta_weather=str(RUTA_WEATHER),
        ruta_salida=str(RUTA_AGRICOLA),
    )

    if df_agricola is None or df_agricola.empty:
        raise ValueError("El dataset agrícola está vacío.")

    validar_columnas(
        df_agricola,
        ["fecha"],
        "dataset agrícola integrado",
    )

    df_agricola["fecha"] = pd.to_datetime(
        df_agricola["fecha"],
        errors="coerce",
    )

    df_agricola = df_agricola.dropna(subset=["fecha"]).copy()
    df_agricola["fecha"] = df_agricola["fecha"].dt.normalize()
    df_agricola = df_agricola.sort_values("fecha").reset_index(drop=True)

    comparar_fechas_sentinel_agricola(df_sentinel, df_agricola)

    print("\nIntegración finalizada.")
    print("Observaciones:", len(df_agricola))
    print("Variables:", len(df_agricola.columns))
    print("\nPrimeras observaciones:")
    print(df_agricola.head().to_string(index=False))

    # --------------------------------------------------------
    # 6. Control de calidad final
    # --------------------------------------------------------
    controlar_dataset_agricola(df_agricola)

    # --------------------------------------------------------
    # 7. Guardar dataset final
    # --------------------------------------------------------
    df_agricola.to_csv(
        RUTA_AGRICOLA,
        index=False,
        encoding="utf-8-sig",
    )

    imprimir_titulo("PROCESO FINALIZADO")
    print("Dataset satelital:", RUTA_SENTINEL)
    print("Dataset meteorológico:", RUTA_WEATHER)
    print("Dataset agrícola:", RUTA_AGRICOLA)
    print(f"\nPeríodo móvil solicitado: {ANIOS_HISTORICOS} años.")
    print("El pipeline terminó correctamente si todos los controles finalizaron sin error.")


if __name__ == "__main__":
    main()
