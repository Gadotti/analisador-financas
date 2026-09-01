"""Caminhos padrão do projeto.

O diretório de dados pode ser redirecionado por PORTFOLIO_DATA_DIR — é assim
que os testes trabalham num diretório temporário, e é a mesma variável que a
aplicação Node respeita.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return Path(os.getenv("PORTFOLIO_DATA_DIR") or (BASE_DIR / "data"))


def history_dir() -> Path:
    return data_dir() / "history"


def portfolio_file() -> Path:
    return data_dir() / "portfolio.json"


def cache_file() -> Path:
    return data_dir() / "cache.json"


def last_analysis_file() -> Path:
    return data_dir() / "last_analysis.json"


def garantir_diretorios() -> None:
    """Cria os diretórios de dados. Chamado antes de qualquer escrita."""
    history_dir().mkdir(parents=True, exist_ok=True)
