from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline

from .features import build_next_observation_pairs, load_integrated_dataset


def _mae(y_true, y_pred):
    return float(mean_absolute_error(y_true, y_pred))


def _metrics(y_true, y_pred, y_persist, names):
    result = {}
    for i, name in enumerate(names):
        result[name] = {
            "mae_rf": _mae(y_true.iloc[:, i], y_pred[:, i]),
            "rmse_rf": float(np.sqrt(mean_squared_error(y_true.iloc[:, i], y_pred[:, i]))),
            "r2_rf": float(r2_score(y_true.iloc[:, i], y_pred[:, i])) if len(y_true) > 1 else None,
            "mae_persistencia": _mae(y_true.iloc[:, i], y_persist[:, i]),
            "mejora_vs_persistencia": bool(
                mean_absolute_error(y_true.iloc[:, i], y_pred[:, i])
                < mean_absolute_error(y_true.iloc[:, i], y_persist[:, i])
            ),
        }
    return result


def _chronological_split(meta: pd.DataFrame):
    dates = pd.Series(pd.to_datetime(meta["fecha_objetivo"]).sort_values().unique())
    if len(dates) < 20:
        raise ValueError("Hay muy pocas fechas objetivo para dividir temporalmente.")
    cut_train = dates.iloc[int(len(dates) * 0.70)]
    cut_val = dates.iloc[int(len(dates) * 0.85)]
    train = pd.to_datetime(meta["fecha_objetivo"]) <= cut_train
    val = (pd.to_datetime(meta["fecha_objetivo"]) > cut_train) & (pd.to_datetime(meta["fecha_objetivo"]) <= cut_val)
    test = pd.to_datetime(meta["fecha_objetivo"]) > cut_val
    if min(int(train.sum()), int(val.sum()), int(test.sum())) < 5:
        raise ValueError("Una partición temporal tiene menos de 5 filas; no es evaluable.")
    return train.to_numpy(), val.to_numpy(), test.to_numpy(), str(cut_train.date()), str(cut_val.date())


def train_real_next_indices(
    dataset_path: str | Path,
    model_path: str | Path,
    reports_dir: str | Path,
    max_gap_days: int = 60,
    min_pixel_fraction: float = 0.60,
):
    raw = load_integrated_dataset(dataset_path)
    X, y, meta = build_next_observation_pairs(
        raw, max_gap_days=max_gap_days, min_pixel_fraction=min_pixel_fraction
    )
    train_mask, val_mask, test_mask, cutoff_train, cutoff_val = _chronological_split(meta)

    # Validación temporal para elegir complejidad sin mirar el test.
    candidates = []
    for depth in (8, 12, None):
        for leaf in (2, 4):
            pipe = Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("rf", RandomForestRegressor(
                    n_estimators=350,
                    max_depth=depth,
                    min_samples_leaf=leaf,
                    max_features=0.85,
                    n_jobs=-1,
                    random_state=42,
                )),
            ])
            pipe.fit(X.loc[train_mask], y.loc[train_mask])
            pred_val = pipe.predict(X.loc[val_mask])
            # Error conjunto escalado para equilibrar NDVI y MSI.
            ranges = y.loc[train_mask].max() - y.loc[train_mask].min()
            ranges = ranges.replace(0, 1).fillna(1)
            mae_by_target = np.abs(y.loc[val_mask].to_numpy() - pred_val).mean(axis=0)
            score = float(np.mean(mae_by_target / ranges.to_numpy()))
            candidates.append((score, depth, leaf))

    candidates.sort(key=lambda x: x[0])
    best_score, best_depth, best_leaf = candidates[0]
    final_model = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("rf", RandomForestRegressor(
            n_estimators=500,
            max_depth=best_depth,
            min_samples_leaf=best_leaf,
            max_features=0.85,
            n_jobs=-1,
            random_state=42,
        )),
    ])
    fit_mask = train_mask | val_mask
    final_model.fit(X.loc[fit_mask], y.loc[fit_mask])

    pred_test = final_model.predict(X.loc[test_mask])
    test_meta = meta.loc[test_mask].reset_index(drop=True)
    test_y = y.loc[test_mask].reset_index(drop=True)
    persistence = test_meta[["NDVI_persistencia", "MSI_persistencia"]].to_numpy()
    metrics = _metrics(test_y, pred_test, persistence, ["NDVI_siguiente", "MSI_siguiente"])

    report_dir = Path(reports_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    model_file = Path(model_path)
    model_file.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": final_model,
        "feature_columns": list(X.columns),
        "targets": ["NDVI_objetivo", "MSI_objetivo"],
        "model_type": "RandomForestRegressor multisalida; siguiente observación Sentinel válida",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_date_range": [str(meta.loc[fit_mask, "fecha_base"].min().date()), str(meta.loc[fit_mask, "fecha_objetivo"].max().date())],
        "max_gap_days": max_gap_days,
        "min_pixel_fraction": min_pixel_fraction,
        "validation_cutoff": cutoff_train,
        "test_start_after": cutoff_val,
        "metrics_test": metrics,
        "selected_params": {"max_depth": best_depth, "min_samples_leaf": best_leaf, "validation_score_scaled_mae": best_score},
        "median_horizon_days": float(meta.loc[fit_mask, "dias_hasta_objetivo"].median()),
        "n_pairs": int(len(X)),
        "warning": "Modelo predictivo experimental de una parcela; no clasifica especie ni fenología.",
    }
    joblib.dump(bundle, model_file)

    pred_report = test_meta[["fecha_base", "fecha_objetivo", "dias_hasta_objetivo"]].copy()
    pred_report["NDVI_real"] = test_y["NDVI_objetivo"]
    pred_report["NDVI_predicho_RF"] = pred_test[:, 0]
    pred_report["NDVI_predicho_persistencia"] = persistence[:, 0]
    pred_report["MSI_real"] = test_y["MSI_objetivo"]
    pred_report["MSI_predicho_RF"] = pred_test[:, 1]
    pred_report["MSI_predicho_persistencia"] = persistence[:, 1]
    pred_report.to_csv(report_dir / "predicciones_test_temporal.csv", index=False, encoding="utf-8-sig")

    with open(report_dir / "metricas_modelo.json", "w", encoding="utf-8") as f:
        json.dump(bundle | {"model": "RandomForestRegressor"}, f, ensure_ascii=False, indent=2, default=str)

    rows = []
    for name, val in metrics.items():
        rows.append({"objetivo": name, **val})
    pd.DataFrame(rows).to_csv(report_dir / "metricas_test.csv", index=False, encoding="utf-8-sig")

    summary = {
        "filas_integradas": int(len(raw)),
        "observaciones_satelitales_validas": int(raw[["NDVI_mean", "MSI_mean"]].dropna().shape[0]),
        "pares_temporales": int(len(X)),
        "train": int(train_mask.sum()),
        "validacion": int(val_mask.sum()),
        "test": int(test_mask.sum()),
        "cutoff_train": cutoff_train,
        "cutoff_validacion": cutoff_val,
        "params": bundle["selected_params"],
        "metrics_test": metrics,
        "modelo": str(model_file),
    }
    with open(report_dir / "resumen_entrenamiento.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\nENTRENAMIENTO COMPLETADO")
    print(f"Filas integradas: {len(raw)}")
    print(f"Pares temporales válidos: {len(X)}")
    print(f"Train / validación / test: {train_mask.sum()} / {val_mask.sum()} / {test_mask.sum()}")
    print("Cortes temporales:", cutoff_train, "|", cutoff_val)
    print("Parámetros seleccionados:", bundle["selected_params"])
    print("\nMétricas del test (comparación con persistencia):")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nModelo guardado en:", model_file)
    print("IMPORTANTE: las métricas son de predicción de índices en la misma parcela, no de rendimiento agronómico.")
    return bundle
