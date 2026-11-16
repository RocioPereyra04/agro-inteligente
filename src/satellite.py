
from pathlib import Path

import ee
import pandas as pd


# ============================================================
# CONFIGURACIÓN SENTINEL-2
# ============================================================

COLECCION_SENTINEL = "COPERNICUS/S2_SR_HARMONIZED"

# Clases SCL que no utilizaremos:
# 0: No data
# 1: Saturated / defective
# 3: Cloud shadows
# 7: Unclassified / low probability cloud
# 8: Medium probability clouds
# 9: High probability clouds
# 10: Cirrus
# 11: Snow / ice

CLASES_SCL_EXCLUIDAS = [0, 1, 3, 7, 8, 9, 10, 11]

# La parcela del proyecto se encuentra en UTM 20S.
CRS_ANALISIS = "EPSG:32720"


# ============================================================
# 1. INICIALIZACIÓN DE EARTH ENGINE
# ============================================================

def inicializar_gee(project_id):

    ee.Initialize(project=project_id)

    print("Google Earth Engine inicializado correctamente.")


# ============================================================
# 2. CREACIÓN DE LA PARCELA
# ============================================================

def crear_parcela(coordenadas):

    parcela = ee.Geometry.Polygon(coordenadas)

    return parcela


# ============================================================
# 3. MÁSCARA DE CALIDAD SCL
# ============================================================

def aplicar_mascara_scl(imagen):

    scl = imagen.select("SCL")

    mascara = scl.neq(0)

    for clase in CLASES_SCL_EXCLUIDAS[1:]:

        mascara = mascara.And(scl.neq(clase))

    return imagen.updateMask(mascara)


# ============================================================
# 4. PREPARACIÓN DE IMÁGENES
# ============================================================

def preparar_imagen(imagen):

    imagen = aplicar_mascara_scl(imagen)

    fecha = ee.Date(
        imagen.get("system:time_start")
    ).format("YYYY-MM-dd")

    return imagen.set("fecha_dia", fecha)


# ============================================================
# 5. CONSTRUCCIÓN DE MOSAICOS DIARIOS
# ============================================================

def crear_mosaico_diario(imagen_representante):

    fecha = ee.String(
        imagen_representante.get("fecha_dia")
    )

    # Recuperar todas las escenas correspondientes al mismo día.
    imagenes_dia = ee.ImageCollection.fromImages(
        ee.List(
            imagen_representante.get("imagenes_dia")
        )
    )

    # mosaic() da prioridad a las últimas imágenes de la colección.
    # Orden descendente por nubosidad:
    # primero las más nubladas y al final las menos nubladas.
    # Así, entre píxeles válidos superpuestos, se prioriza
    # la escena con menor nubosidad de escena.
    mosaico = (
        imagenes_dia
        .sort("CLOUDY_PIXEL_PERCENTAGE", False)
        .mosaic()
    )

    return mosaico.set({
        "fecha_dia": fecha,
        "system:time_start": ee.Date.parse(
            "YYYY-MM-dd", fecha
        ).millis(),
        "escenas_mosaico": imagenes_dia.size(),
        "imagen_id": ee.String("MOSAICO_").cat(fecha)
    })


def generar_mosaicos_diarios(coleccion):

    # Una imagen representativa por fecha.
    fechas_unicas = coleccion.distinct("fecha_dia")

    # Relacionar cada fecha con todas sus escenas.
    condicion = ee.Filter.equals(
        leftField="fecha_dia",
        rightField="fecha_dia"
    )

    union = ee.Join.saveAll(
        "imagenes_dia"
    ).apply(
        primary=fechas_unicas,
        secondary=coleccion,
        condition=condicion
    )

    # Crear un mosaico por fecha.
    mosaicos = ee.ImageCollection(union).map(
        crear_mosaico_diario
    )

    return mosaicos.sort("system:time_start")


# ============================================================
# 6. CÁLCULO DE NDVI Y MSI
# ============================================================

def calcular_indices(imagen):

    banda_roja = imagen.select("B4")
    banda_nir = imagen.select("B8")
    banda_swir = imagen.select("B11")

    # NDVI = (B8 - B4) / (B8 + B4)

    denominador_ndvi = banda_nir.add(banda_roja)

    ndvi = (
        banda_nir.subtract(banda_roja)
        .divide(denominador_ndvi)
        .updateMask(denominador_ndvi.neq(0))
        .rename("NDVI")
    )

    # MSI = B11 / B8
    # B8 debe ser mayor que cero.

    msi = (
        banda_swir.divide(
            banda_nir.updateMask(banda_nir.gt(0))
        )
        .rename("MSI")
    )

    return imagen.addBands([ndvi, msi])


# ============================================================
# 7. EXTRACCIÓN DE ESTADÍSTICAS
# ============================================================

def extraer_estadisticas(imagen, parcela, escala=20):

    imagen_indices = calcular_indices(imagen)

    # Estadísticas para NDVI y MSI.
    reductor = (
        ee.Reducer.mean()
        .combine(
            reducer2=ee.Reducer.stdDev(),
            sharedInputs=True
        )
        .combine(
            reducer2=ee.Reducer.minMax(),
            sharedInputs=True
        )
        .combine(
            reducer2=ee.Reducer.count(),
            sharedInputs=True
        )
    )

    estadisticas = imagen_indices.select(
        ["NDVI", "MSI"]
    ).reduceRegion(
        reducer=reductor,
        geometry=parcela,
        scale=escala,
        crs=CRS_ANALISIS,
        maxPixels=1e9,
        tileScale=4
    )

    fecha = ee.String(
        imagen.get("fecha_dia")
    )

    propiedades = {
        "fecha": fecha,
        "imagen_id": imagen.get("imagen_id"),
        "escenas_mosaico": imagen.get("escenas_mosaico")
    }

    return ee.Feature(
        None,
        estadisticas
    ).set(propiedades)


# ============================================================
# 8. OBTENER DATASET SATELITAL
# ============================================================

def obtener_dataset_satelital(
    parcela,
    fecha_inicio,
    fecha_fin,
    salida_csv,
    max_nubosidad=100,
    escala=20
):

    print("\nBuscando imágenes Sentinel-2...")

    coleccion = (
        ee.ImageCollection(COLECCION_SENTINEL)
        .filterBounds(parcela)
        .filterDate(fecha_inicio, fecha_fin)
        .filter(
            ee.Filter.lt(
                "CLOUDY_PIXEL_PERCENTAGE",
                max_nubosidad
            )
        )
    )

    cantidad_escenas = coleccion.size().getInfo()

    print("Escenas Sentinel encontradas:", cantidad_escenas)

    if cantidad_escenas == 0:

        raise ValueError(
            "No se encontraron imágenes Sentinel-2 "
            "para la parcela y período indicados."
        )

    # Aplicar máscara y asignar fecha de adquisición.
    coleccion_preparada = coleccion.map(
        preparar_imagen
    )

    # Construir mosaicos diarios.
    print("\nConstruyendo mosaicos diarios...")

    mosaicos = generar_mosaicos_diarios(
        coleccion_preparada
    )

    cantidad_mosaicos = mosaicos.size().getInfo()

    print("Mosaicos diarios:", cantidad_mosaicos)

    if cantidad_mosaicos == 0:

        raise ValueError(
            "No se pudieron construir mosaicos diarios."
        )

    # Convertir cada mosaico en una Feature con estadísticas.
    lista_mosaicos = mosaicos.toList(cantidad_mosaicos)

    features = ee.FeatureCollection(
        lista_mosaicos.map(
            lambda elemento: extraer_estadisticas(
                ee.Image(elemento),
                parcela,
                escala
            )
        )
    )

    print("\nExtrayendo estadísticas de la parcela...")

    resultado = features.getInfo()

    filas = [
        feature["properties"]
        for feature in resultado["features"]
    ]

    df = pd.DataFrame(filas)

    if df.empty:

        raise ValueError(
            "No se pudieron extraer estadísticas satelitales."
        )

    # Conversión y ordenamiento de fechas.
    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce"
    )

    df = (
        df.dropna(subset=["fecha"])
        .sort_values("fecha")
        .reset_index(drop=True)
    )

    # Control: una fila por fecha.
    duplicados = df.duplicated(
        subset=["fecha"]
    ).sum()

    if duplicados > 0:

        raise ValueError(
            f"Se encontraron {duplicados} fechas duplicadas "
            "después de construir los mosaicos."
        )

    # Guardar CSV.
    ruta = Path(salida_csv)

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nDataset satelital guardado correctamente.")

    print("Ruta:", ruta)
    print("Escenas originales:", cantidad_escenas)
    print("Mosaicos diarios:", cantidad_mosaicos)
    print("Observaciones finales:", len(df))
    print("Fechas duplicadas:", duplicados)

    print("\nEscenas por mosaico:")
    print(df["escenas_mosaico"].describe())

    return df
