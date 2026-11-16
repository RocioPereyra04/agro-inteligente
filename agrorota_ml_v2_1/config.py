from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DATASET_AGRICOLA = PROJECT_ROOT / "data" / "processed" / "dataset_agricola.csv"
WEATHER_DAILY = PROJECT_ROOT / "data" / "processed" / "weather_parcela.csv"
FORECAST_CSV = PROJECT_ROOT / "data" / "processed" / "weather_forecast.csv"
CROP_CATALOG = ROOT / "inputs" / "cultivos_seleccionados.csv"
CROP_CALENDAR = ROOT / "inputs" / "calendario_etapas_mensuales.csv"
MODEL_PATH = ROOT / "models" / "rf_predice_indices.joblib"
REPORTS_DIR = ROOT / "reports"

# Completar con el centroide de la parcela ya definida en basededatos.py.
# No se inventa la ubicación. El centroide es necesario para calcular Ra y ETo.
LATITUD_PARCELA = None

# Texturas que se manejan como escenarios alternativos hasta confirmar el suelo.
SUELOS_ESCENARIO = ["arenoso", "franco-limoso"]

# Se utiliza el siguiente registro satelital válido como objetivo. Los intervalos
# demasiado largos no representan una evolución temporal comparable.
MAX_GAP_DAYS = 60
MIN_VALID_PIXEL_FRACTION = 0.60
RANDOM_STATE = 42
