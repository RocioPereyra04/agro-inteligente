from pathlib import Path
import argparse

from config import DATASET_AGRICOLA, MODEL_PATH, REPORTS_DIR, MAX_GAP_DAYS, MIN_VALID_PIXEL_FRACTION
from src.train import train_real_next_indices


def main():
    parser = argparse.ArgumentParser(description="Entrena Random Forest para predecir el siguiente NDVI/MSI observado.")
    parser.add_argument("--dataset", default=str(DATASET_AGRICOLA))
    parser.add_argument("--modelo", default=str(MODEL_PATH))
    parser.add_argument("--reportes", default=str(REPORTS_DIR))
    parser.add_argument("--max-gap", type=int, default=MAX_GAP_DAYS)
    parser.add_argument("--min-pixel-fraction", type=float, default=MIN_VALID_PIXEL_FRACTION)
    args = parser.parse_args()
    train_real_next_indices(args.dataset, args.modelo, args.reportes, args.max_gap, args.min_pixel_fraction)


if __name__ == "__main__":
    main()
