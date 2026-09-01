"""Caminhos padrão do projeto."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
WEB_DIR = BASE_DIR / "web"
HISTORY_DIR = DATA_DIR / "history"

PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
CACHE_FILE = DATA_DIR / "cache.json"
LAST_ANALYSIS_FILE = DATA_DIR / "last_analysis.json"

for _d in (DATA_DIR, HISTORY_DIR):
    _d.mkdir(parents=True, exist_ok=True)
