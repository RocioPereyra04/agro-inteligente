import argparse
from pathlib import Path

from config import DATASET_AGRICOLA, WEATHER_DAILY, FORECAST_CSV, MODEL_PATH, REPORTS_DIR, CROP_CATALOG, CROP_CALENDAR, LATITUD_PARCELA
from src.inference import run_inference


def main():
    parser = argparse.ArgumentParser(description="Carga el RF y genera el estado de parcela, rotación y riego demo.")
    parser.add_argument("--dataset", default=str(DATASET_AGRICOLA))
    parser.add_argument("--modelo", default=str(MODEL_PATH))
    parser.add_argument("--reportes", default=str(REPORTS_DIR))
    parser.add_argument("--cultivo-actual", default=None, help="Lechuga, Zapallo coreano*, Frutilla, Naranja / cítricos, Melón, Sandía o Ciruelo (según catálogo: Spondias purpurea)")
    parser.add_argument("--weather", default=str(WEATHER_DAILY))
    parser.add_argument("--forecast", default=str(FORECAST_CSV))
    parser.add_argument("--latitud", type=float, default=LATITUD_PARCELA)
    parser.add_argument("--fase-riego", choices=["inicio", "medio", "final"], default=None)
    args = parser.parse_args()
    if not Path(args.modelo).exists():
        raise SystemExit(
            f"No existe el modelo entrenado: {args.modelo}. "
            "Primero ejecutá train_model.py con data/processed/dataset_agricola.csv."
        )
    run_inference(
        dataset_path=args.dataset,
        model_path=args.modelo,
        reports_dir=args.reportes,
        calendar_path=CROP_CALENDAR,
        catalog_path=CROP_CATALOG,
        current_crop=args.cultivo_actual,
        weather_path=args.weather if Path(args.weather).exists() else None,
        forecast_path=args.forecast if Path(args.forecast).exists() else None,
        latitude=args.latitud,
        irrigation_phase=args.fase_riego,
    )


if __name__ == "__main__":
    main()
