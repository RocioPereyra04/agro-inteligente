# ============================================================
# src/analysis.py - EDA y analisis de estacionalidad
# ============================================================

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parents[1]
RUTA_DATASET = BASE_DIR / "data/processed/dataset_agricola.csv"
CARPETA_EDA = BASE_DIR / "data/processed/eda"
COLUMNA_FECHA = "fecha"

VARIABLES_PRINCIPALES = [
    "NDVI_mean", "MSI_mean",
    "precipitacion_acumulada_7d_mm",
    "precipitacion_acumulada_30d_mm",
    "temperatura_maxima_30d_c",
    "temperatura_minima_30d_c",
]

VARIABLES_CORRELACION = [
    "NDVI_mean", "NDVI_stdDev", "MSI_mean", "MSI_stdDev",
    "precipitacion_acumulada_7d_mm",
    "precipitacion_acumulada_30d_mm",
    "temperatura_media_7d_c", "temperatura_maxima_7d_c",
    "temperatura_minima_7d_c", "temperatura_media_30d_c",
    "temperatura_maxima_30d_c", "temperatura_minima_30d_c",
]


def crear_directorios(carpeta_salida):
    carpeta_salida = Path(carpeta_salida)
    carpeta_graficos = carpeta_salida / "graficos"
    carpeta_graficos.mkdir(parents=True, exist_ok=True)
    return carpeta_salida, carpeta_graficos


def guardar_grafico(figura, ruta):
    figura.tight_layout()
    figura.savefig(ruta, dpi=250, bbox_inches="tight")
    plt.close(figura)


def cargar_dataset(ruta_csv, carpeta_salida):
    """Carga el CSV y conserva las filas cuya fecha no pudo convertirse."""
    ruta_csv = Path(ruta_csv)
    if not ruta_csv.exists():
        raise FileNotFoundError(f"No se encontro el archivo: {ruta_csv}")

    df = pd.read_csv(ruta_csv)
    if COLUMNA_FECHA not in df.columns:
        raise ValueError(f"No existe la columna '{COLUMNA_FECHA}'.")

    fechas = pd.to_datetime(df[COLUMNA_FECHA], errors="coerce")
    invalidas = fechas.isna()

    if invalidas.any():
        df.loc[invalidas].to_csv(
            carpeta_salida / "filas_con_fecha_invalida.csv", index=False
        )

    print(f"\nFilas originales: {len(df)}")
    print(f"Fechas invalidas: {int(invalidas.sum())}")
    print(f"Fechas validas: {int(fechas.notna().sum())}")

    df[COLUMNA_FECHA] = fechas
    df = df.dropna(subset=[COLUMNA_FECHA]).copy()
    return df.sort_values(COLUMNA_FECHA).reset_index(drop=True)


def analizar_calidad(df, carpeta_salida):
    faltantes = pd.DataFrame({
        "variable": df.columns,
        "cantidad_faltantes": df.isna().sum().values,
        "porcentaje_faltantes": (df.isna().mean().values * 100).round(2)
    }).sort_values("porcentaje_faltantes", ascending=False)

    faltantes.to_csv(carpeta_salida / "valores_faltantes.csv", index=False)

    print("\nCALIDAD DE DATOS")
    print(f"Duplicados completos: {int(df.duplicated().sum())}")
    print(
        "Filas involucradas en fechas repetidas: "
        f"{int(df.duplicated(subset=[COLUMNA_FECHA], keep=False).sum())}"
    )
    print(f"Desde: {df[COLUMNA_FECHA].min()}")
    print(f"Hasta: {df[COLUMNA_FECHA].max()}")
    print(faltantes.to_string(index=False))
    return faltantes


def analizar_estadisticas(df, carpeta_salida):
    numericas = df.select_dtypes(include=np.number)
    estadisticas = numericas.describe().T
    estadisticas["mediana"] = numericas.median()
    estadisticas["varianza"] = numericas.var()
    estadisticas = estadisticas.round(4)
    estadisticas.to_csv(carpeta_salida / "resumen_estadistico.csv")
    print("\nESTADISTICA DESCRIPTIVA")
    print(estadisticas)
    return estadisticas


def analizar_evolucion_temporal(df, carpeta_graficos):
    for variable in VARIABLES_PRINCIPALES:
        if variable not in df.columns:
            print(f"Aviso: no existe '{variable}'. Se omite.")
            continue
        datos = df[[COLUMNA_FECHA, variable]].dropna()
        if datos.empty:
            continue

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(datos[COLUMNA_FECHA], datos[variable],
                marker="o", markersize=3, linewidth=1)
        ax.set(title=f"Evolucion temporal de {variable}",
               xlabel="Fecha", ylabel=variable)
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis="x", rotation=30)
        guardar_grafico(fig, carpeta_graficos / f"temporal_{variable}.png")

    if all(v in df.columns for v in ["NDVI_mean", "MSI_mean"]):
        fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        for ax, variable in zip(axes, ["NDVI_mean", "MSI_mean"]):
            ax.plot(df[COLUMNA_FECHA], df[variable],
                    marker="o", markersize=3)
            ax.set_title(f"Evolucion de {variable}")
            ax.set_ylabel(variable)
            ax.grid(True, alpha=0.3)
        axes[-1].set_xlabel("Fecha")
        guardar_grafico(fig, carpeta_graficos / "evolucion_NDVI_MSI.png")


def analizar_distribuciones(df, carpeta_graficos):
    for variable in df.select_dtypes(include=np.number).columns:
        datos = df[variable].dropna()
        if datos.empty:
            continue

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(datos, bins=20, edgecolor="black")
        ax.set(title=f"Distribucion de {variable}",
               xlabel=variable, ylabel="Frecuencia")
        ax.grid(True, alpha=0.2)
        guardar_grafico(fig, carpeta_graficos / f"histograma_{variable}.png")

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.boxplot(datos, vert=False)
        ax.set(title=f"Diagrama de caja de {variable}", xlabel=variable)
        guardar_grafico(fig, carpeta_graficos / f"boxplot_{variable}.png")


def analizar_correlaciones(df, carpeta_salida, carpeta_graficos):
    columnas = [
        c for c in VARIABLES_CORRELACION
        if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
    ]
    datos = df[columnas].copy()
    # Pearson no esta definido para variables constantes.
    datos = datos.loc[:, datos.nunique(dropna=True) > 1]

    if datos.shape[1] < 2:
        print("No hay suficientes variables para calcular correlaciones.")
        return pd.DataFrame()

    correlaciones = datos.corr(method="pearson")
    correlaciones.to_csv(carpeta_salida / "correlaciones.csv")
    print("\nCORRELACIONES DE PEARSON")
    print(correlaciones.round(3))

    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(correlaciones, cmap="coolwarm", vmin=-1, vmax=1,
                   aspect="auto")
    ax.set_xticks(range(len(correlaciones.columns)))
    ax.set_yticks(range(len(correlaciones.index)))
    ax.set_xticklabels(correlaciones.columns, rotation=90)
    ax.set_yticklabels(correlaciones.index)
    fig.colorbar(im, ax=ax, label="Correlacion de Pearson")
    ax.set_title("Matriz de correlacion")
    guardar_grafico(fig, carpeta_graficos / "matriz_correlaciones.png")
    return correlaciones


def detectar_valores_atipicos(df, carpeta_salida):
    resultados = []
    for variable in df.select_dtypes(include=np.number).columns:
        datos = df[variable].dropna()
        if len(datos) < 4:
            continue
        q1, q3 = datos.quantile([0.25, 0.75])
        iqr = q3 - q1
        inferior = q1 - 1.5 * iqr
        superior = q3 + 1.5 * iqr
        mascara = (df[variable] < inferior) | (df[variable] > superior)
        cantidad = int(mascara.sum())
        resultados.append({
            "variable": variable,
            "limite_inferior": inferior,
            "limite_superior": superior,
            "cantidad_atipicos": cantidad,
            "porcentaje_atipicos": cantidad / len(datos) * 100
        })

    resultado = pd.DataFrame(resultados)
    resultado.to_csv(carpeta_salida / "valores_atipicos.csv", index=False)
    return resultado


def diagnosticar_observaciones(df, carpeta_salida):
    columnas = [
        COLUMNA_FECHA, "NDVI_mean", "MSI_mean", "NDVI_count",
        "MSI_count", "escenas_mosaico",
        "precipitacion_acumulada_30d_mm"
    ]
    datos = df[[c for c in columnas if c in df.columns]].copy()
    condiciones = []

    if "NDVI_count" in datos:
        datos["calidad_pixeles"] = np.where(
            datos["NDVI_count"] < 15, "REVISAR", "ACEPTABLE"
        )
        condiciones.append(datos["calidad_pixeles"].eq("REVISAR"))

    if "NDVI_mean" in datos:
        datos["NDVI_bajo"] = datos["NDVI_mean"] < 0.10
        condiciones.append(datos["NDVI_bajo"].fillna(False))

    if condiciones:
        mascara = condiciones[0].copy()
        for condicion in condiciones[1:]:
            mascara |= condicion
        observaciones = datos.loc[mascara].copy()
    else:
        observaciones = datos.iloc[0:0].copy()

    observaciones.to_csv(
        carpeta_salida / "observaciones_para_revisar.csv", index=False
    )
    print(f"\nObservaciones marcadas para revisar: {len(observaciones)}")
    if not observaciones.empty:
        print(observaciones.to_string(index=False))
    return observaciones


def analizar_estacionalidad(df, carpeta_salida, carpeta_graficos):
    """Resume las fechas Sentinel disponibles por año y mes."""
    variables = [v for v in ["NDVI_mean", "MSI_mean"] if v in df.columns]
    if not variables:
        print("No se encontraron variables NDVI_mean o MSI_mean.")
        return pd.DataFrame(), pd.DataFrame()

    datos = df[[COLUMNA_FECHA] + variables].copy()
    datos["anio"] = datos[COLUMNA_FECHA].dt.year
    datos["mes"] = datos[COLUMNA_FECHA].dt.month

    mensual_anual = datos.groupby(["anio", "mes"])[variables].agg(
        ["mean", "median", "count"]
    )
    mensual_anual.to_csv(
        carpeta_salida / "resumen_mensual_por_anio.csv"
    )

    climatologia = datos.groupby("mes")[variables].agg(
        ["mean", "median", "std", "count"]
    )
    climatologia.to_csv(carpeta_salida / "climatologia_mensual.csv")

    conteos = datos.pivot_table(
        index="mes", columns="anio", values=variables[0], aggfunc="count"
    ).fillna(0).astype(int)
    conteos.to_csv(carpeta_salida / "cantidad_observaciones_mes_anio.csv")

    print("\nCANTIDAD DE OBSERVACIONES POR MES Y ANIO")
    print(conteos)

    nombres_meses = [
        "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"
    ]

    for variable in variables:
        tabla = datos.pivot_table(
            index="mes", columns="anio", values=variable, aggfunc="mean"
        )
        fig, ax = plt.subplots(figsize=(11, 5))
        for anio in tabla.columns:
            ax.plot(tabla.index, tabla[anio], marker="o", label=str(anio))
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(nombres_meses)
        ax.set(title=f"{variable}: comparacion mensual entre anios",
               xlabel="Mes", ylabel=variable)
        ax.grid(True, alpha=0.3)
        ax.legend(title="Anio")
        guardar_grafico(
            fig, carpeta_graficos / f"estacionalidad_{variable}.png"
        )

        serie = datos.groupby("mes")[variable].mean()
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(serie.index, serie.values, marker="o")
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(nombres_meses)
        ax.set(title=f"Promedio mensual historico de {variable}",
               xlabel="Mes", ylabel=variable)
        ax.grid(True, alpha=0.3)
        guardar_grafico(
            fig, carpeta_graficos / f"climatologia_{variable}.png"
        )

    return mensual_anual, climatologia


def ejecutar_eda(ruta_csv=RUTA_DATASET, carpeta_salida=CARPETA_EDA):
    carpeta_salida, carpeta_graficos = crear_directorios(carpeta_salida)

    print("\n" + "=" * 60)
    print("ETAPA 2 - ANALISIS EXPLORATORIO DE DATOS")
    print("=" * 60)

    df = cargar_dataset(ruta_csv, carpeta_salida)
    faltantes = analizar_calidad(df, carpeta_salida)
    estadisticas = analizar_estadisticas(df, carpeta_salida)

    analizar_evolucion_temporal(df, carpeta_graficos)
    analizar_distribuciones(df, carpeta_graficos)
    correlaciones = analizar_correlaciones(
        df, carpeta_salida, carpeta_graficos
    )
    atipicos = detectar_valores_atipicos(df, carpeta_salida)
    revision = diagnosticar_observaciones(df, carpeta_salida)
    mensual_anual, climatologia = analizar_estacionalidad(
        df, carpeta_salida, carpeta_graficos
    )

    print("\n" + "=" * 60)
    print("EDA FINALIZADO")
    print(f"Resultados: {carpeta_salida.resolve()}")
    print("=" * 60)

    return {
        "dataset": df,
        "faltantes": faltantes,
        "estadisticas": estadisticas,
        "correlaciones": correlaciones,
        "atipicos": atipicos,
        "observaciones_revision": revision,
        "mensual_anual": mensual_anual,
        "climatologia": climatologia,
    }


if __name__ == "__main__":
    ejecutar_eda()
