from __future__ import annotations

import math
import pandas as pd

from config import DATASET_AGRICOLA, MIN_VALID_PIXEL_FRACTION, MAX_GAP_DAYS
from src.features import (
    load_integrated_dataset,
    valid_satellite_observations,
    build_next_observation_pairs,
)


def main():
    print("\nDIAGNÓSTICO DEL DATASET AGRO ROTA")
    print("================================")
    df = load_integrated_dataset(DATASET_AGRICOLA)
    valid_raw = df.dropna(subset=["NDVI_mean", "MSI_mean"])
    quality = valid_satellite_observations(df, MIN_VALID_PIXEL_FRACTION)

    print(f"Filas integradas: {len(df)}")
    print(f"Fechas: {df['fecha'].min().date()} -> {df['fecha'].max().date()}")
    print(f"Filas con NDVI y MSI: {len(valid_raw)}")
    print(f"Observaciones tras filtro de calidad ({MIN_VALID_PIXEL_FRACTION:.0%}): {len(quality)}")
    if len(quality) > 1:
        gaps = quality["fecha"].diff().dt.days.dropna()
        print(f"Intervalo entre observaciones válidas (días): mediana={gaps.median():.1f}; máximo={gaps.max()}")

    climate_groups = {
        "precipitación 7/30 días": ["precip_7d_mm", "precip_30d_mm"],
        "temperatura media 7/30 días": ["temp_mean_7d_c", "temp_mean_30d_c"],
    }
    for label, columns in climate_groups.items():
        available = [c for c in columns if c in df.columns]
        if not available:
            print(f"{label}: FALTAN COLUMNAS {columns}")
        else:
            for col in available:
                print(f"  {col}: {df[col].notna().sum()}/{len(df)} valores")

    try:
        X, y, meta = build_next_observation_pairs(
            df,
            max_gap_days=MAX_GAP_DAYS,
            min_pixel_fraction=MIN_VALID_PIXEL_FRACTION,
        )
        print(f"Pares temporales entrenables: {len(X)}")
        print(f"Horizonte entre imágenes (días): mediana={meta['dias_hasta_objetivo'].median():.1f}; máximo={meta['dias_hasta_objetivo'].max()}")
        print("Estado: apto para intentar entrenamiento temporal.")
    except Exception as exc:
        print("Estado: NO apto todavía para entrenamiento.")
        print("Motivo:", exc)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
