"""Prueba funcional local del módulo de alertas con datos sintéticos controlados.
No representa resultados de la parcela real."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.diagnostics import generate_agronomic_alerts


def make_history(pattern="normal"):
    dates = pd.date_range("2024-01-01", periods=36, freq="15D")
    rng = np.random.default_rng(7)
    ndvi = 0.35 + 0.04 * np.sin(np.arange(36) * 2 * np.pi / 24) + rng.normal(0, 0.008, 36)
    msi = 1.00 + 0.08 * np.cos(np.arange(36) * 2 * np.pi / 24) + rng.normal(0, 0.012, 36)
    rain = rng.uniform(0, 18, 36)
    temp = rng.uniform(15, 24, 36)

    if pattern == "combined_stress":
        ndvi[-6:] -= np.linspace(0.00, 0.17, 6)
        msi[-6:] += np.linspace(0.00, 0.45, 6)
        rain[-6:] = 25.0
    elif pattern == "low_vigor":
        ndvi[-1] = 0.08
        msi[-1] = 0.85
        rain[-1] = 15.0
    elif pattern == "heavy_rain":
        rain[-1] = 80.0
        ndvi[-1] = ndvi[-2] - 0.08

    df = pd.DataFrame({
        "fecha": dates,
        "NDVI_mean": ndvi,
        "MSI_mean": msi,
        "precip_7d_mm": rain,
        "precip_30d_mm": rain * 2.4,
        "temp_mean_7d_c": temp,
        "ndvi_change_per_day": pd.Series(ndvi).diff() / 15,
        "msi_change_per_day": pd.Series(msi).diff() / 15,
    })
    return df


def main():
    for pattern in ("normal", "combined_stress", "low_vigor", "heavy_rain"):
        alerts, summary = generate_agronomic_alerts(make_history(pattern))
        assert not alerts.empty
        assert "codigo" in alerts.columns
        print(pattern, "->", alerts["codigo"].tolist())
        print("alertas:", summary["numero_alertas"])
    print("Prueba funcional de diagnósticos: OK")


if __name__ == "__main__":
    main()
