from __future__ import annotations

from pathlib import Path
import unicodedata
import numpy as np
import pandas as pd


ALIASES = {
    "fecha": ["fecha", "date", "datetime"],
    "NDVI_mean": ["NDVI_mean", "ndvi_mean", "ndvi"],
    "MSI_mean": ["MSI_mean", "msi_mean", "msi"],
    "NDVI_stdDev": ["NDVI_stdDev", "ndvi_stddev", "ndvi_std", "ndvi_stddev_mean"],
    "MSI_stdDev": ["MSI_stdDev", "msi_stddev", "msi_std", "msi_stddev_mean"],
    "NDVI_count": ["NDVI_count", "ndvi_count"],
    "MSI_count": ["MSI_count", "msi_count"],
    "precip_7d_mm": ["precipitacion_acumulada_7d_mm", "precip_7d_mm", "precipitacion_7d_mm"],
    "precip_30d_mm": ["precipitacion_acumulada_30d_mm", "precip_30d_mm", "precipitacion_30d_mm"],
    "temp_mean_7d_c": ["temperatura_media_7d_c", "temp_mean_7d_c"],
    "temp_max_7d_c": ["temperatura_maxima_7d_c", "temp_max_7d_c"],
    "temp_min_7d_c": ["temperatura_minima_7d_c", "temp_min_7d_c"],
    "temp_mean_30d_c": ["temperatura_media_30d_c", "temp_mean_30d_c"],
    "temp_max_30d_c": ["temperatura_maxima_30d_c", "temp_max_30d_c"],
    "temp_min_30d_c": ["temperatura_minima_30d_c", "temp_min_30d_c"],
}

BASE_FEATURES = [
    "NDVI_mean", "MSI_mean", "NDVI_stdDev", "MSI_stdDev",
    "NDVI_count", "MSI_count",
    "precip_7d_mm", "precip_30d_mm",
    "temp_mean_7d_c", "temp_max_7d_c", "temp_min_7d_c",
    "temp_mean_30d_c", "temp_max_30d_c", "temp_min_30d_c",
    "ndvi_change_per_day", "msi_change_per_day",
    "days_since_previous_valid", "doy_sin", "doy_cos",
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in s.lower() if ch.isalnum())


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    lookup = {_norm(c): c for c in out.columns}
    rename = {}
    for canonical, candidates in ALIASES.items():
        if canonical in out.columns:
            continue
        for candidate in candidates:
            original = lookup.get(_norm(candidate))
            if original is not None:
                rename[original] = canonical
                break
    return out.rename(columns=rename)


def load_integrated_dataset(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No encuentro {path}. Primero ejecutá basededatos.py para generar "
            "data/processed/dataset_agricola.csv."
        )
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = canonicalize_columns(df)
    required = ["fecha", "NDVI_mean", "MSI_mean"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en dataset_agricola.csv: {missing}")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.normalize()
    if df["fecha"].isna().any():
        raise ValueError("Hay fechas inválidas en dataset_agricola.csv")
    if df["fecha"].duplicated().any():
        dates = df.loc[df["fecha"].duplicated(keep=False), "fecha"].astype(str).tolist()[:10]
        raise ValueError(f"Hay fechas duplicadas en el dataset integrado: {dates}")
    for c in df.columns:
        if c != "fecha":
            converted = pd.to_numeric(df[c], errors="coerce")
            # Reemplazar únicamente si la columna contiene valores numéricos.
            if converted.notna().any() or df[c].isna().all():
                df[c] = converted.replace([-999, -999.0, -9999, -9999.0, np.inf, -np.inf], np.nan)
    return df.sort_values("fecha").reset_index(drop=True)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("fecha").reset_index(drop=True)
    doy = out["fecha"].dt.dayofyear.astype(float)
    out["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # Índices de la observación válida anterior: permiten identificar tendencias.
    ndvi = pd.to_numeric(out["NDVI_mean"], errors="coerce")
    msi = pd.to_numeric(out["MSI_mean"], errors="coerce")
    previous_date = out["fecha"].shift(1)
    gap = (out["fecha"] - previous_date).dt.days
    gap = gap.replace(0, np.nan)
    out["days_since_previous_valid"] = gap
    out["ndvi_change_per_day"] = (ndvi - ndvi.shift(1)) / gap
    out["msi_change_per_day"] = (msi - msi.shift(1)) / gap

    # Mantener las columnas opcionales para que el pipeline tenga esquema estable.
    for c in BASE_FEATURES:
        if c not in out.columns:
            out[c] = np.nan
    for c in BASE_FEATURES:
        out[c] = pd.to_numeric(out[c], errors="coerce")
        out[c] = out[c].replace([np.inf, -np.inf], np.nan)
    return out


def valid_satellite_observations(df: pd.DataFrame, min_pixel_fraction: float = 0.60) -> pd.DataFrame:
    out = df.dropna(subset=["NDVI_mean", "MSI_mean"]).copy()
    # No tratar los NaN como cero. Filtrar observaciones con muy pocos píxeles.
    count_cols = [c for c in ("NDVI_count", "MSI_count") if c in out.columns]
    if count_cols:
        maxima = [pd.to_numeric(out[c], errors="coerce").max() for c in count_cols]
        maxima = [x for x in maxima if pd.notna(x) and x > 0]
        if maxima:
            reference = max(maxima)
            threshold = int(np.ceil(reference * min_pixel_fraction))
            for c in count_cols:
                out = out[pd.to_numeric(out[c], errors="coerce").fillna(0) >= threshold]
    return out.sort_values("fecha").reset_index(drop=True)


def build_feature_table(raw: pd.DataFrame, min_pixel_fraction: float = 0.60) -> pd.DataFrame:
    # Primero se eliminan observaciones sin índices/píxeles suficientes; después se
    # calculan las diferencias respecto de la observación válida anterior.
    df = valid_satellite_observations(raw, min_pixel_fraction=min_pixel_fraction)
    if df.empty:
        raise ValueError("No quedan observaciones Sentinel con NDVI/MSI y píxeles válidos.")
    df = add_time_features(df)
    # Asegurar columnas, incluso si el CSV no contenía desviaciones/counts.
    for c in BASE_FEATURES:
        if c not in df.columns:
            df[c] = np.nan
    return df


def build_next_observation_pairs(
    raw: pd.DataFrame,
    max_gap_days: int = 60,
    min_pixel_fraction: float = 0.60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """X(t) -> [NDVI, MSI] de la siguiente observación válida Sentinel.

    El objetivo es real (el índice medido en la siguiente imagen), no una etiqueta
    agronómica inventada. La distancia entre observaciones se guarda como metadato.
    """
    obs = build_feature_table(raw, min_pixel_fraction=min_pixel_fraction)
    obs = obs.sort_values("fecha").reset_index(drop=True)
    meta = pd.DataFrame({
        "fecha_base": obs["fecha"],
        "fecha_objetivo": obs["fecha"].shift(-1),
        "dias_hasta_objetivo": (obs["fecha"].shift(-1) - obs["fecha"]).dt.days,
        "NDVI_objetivo": obs["NDVI_mean"].shift(-1),
        "MSI_objetivo": obs["MSI_mean"].shift(-1),
        "NDVI_persistencia": obs["NDVI_mean"],
        "MSI_persistencia": obs["MSI_mean"],
    })
    mask = (
        meta["fecha_objetivo"].notna()
        & meta["dias_hasta_objetivo"].between(1, max_gap_days)
        & meta["NDVI_objetivo"].notna()
        & meta["MSI_objetivo"].notna()
    )
    X = obs.loc[mask, BASE_FEATURES].reset_index(drop=True)
    y = meta.loc[mask, ["NDVI_objetivo", "MSI_objetivo"]].reset_index(drop=True)
    meta = meta.loc[mask].reset_index(drop=True)
    if len(X) < 60:
        raise ValueError(
            f"Solo se formaron {len(X)} pares temporales. Se necesitan al menos 60 "
            "para una demo razonable. Revisá cobertura de píxeles, ventanas y MAX_GAP_DAYS."
        )
    # Eliminar predictores sin ningún dato; los restantes se imputan dentro del Pipeline.
    usable = [c for c in X.columns if X[c].notna().any()]
    X = X[usable]
    required_groups = [
        ("precipitación", ["precip_7d_mm", "precip_30d_mm"]),
        ("temperatura", ["temp_mean_7d_c", "temp_mean_30d_c"]),
    ]
    missing_groups = [label for label, cols in required_groups if not any(c in X.columns for c in cols)]
    if missing_groups:
        raise ValueError(
            "El dataset integrado no contiene variables climáticas válidas para: "
            + ", ".join(missing_groups)
            + ". Revisá que basededatos.py haya integrado las ventanas NASA POWER de 7/30 días."
        )
    return X, y, meta


def latest_feature_row(raw: pd.DataFrame, feature_columns: list[str], min_pixel_fraction: float = 0.60):
    obs = build_feature_table(raw, min_pixel_fraction=min_pixel_fraction)
    latest = obs.iloc[[-1]].copy()
    for c in feature_columns:
        if c not in latest.columns:
            latest[c] = np.nan
    return latest[feature_columns], latest.iloc[0]
