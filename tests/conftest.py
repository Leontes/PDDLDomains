"""Utilidades comunes de los tests."""

from collections.abc import Callable
from pathlib import Path

import pytest

from pddldomains.analysis import Analyzer, CollectionAnalysis
from pddldomains.catalog import Catalog

type Writer = Callable[[str, str], Path]


@pytest.fixture(autouse=True)
def english(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los tests esperan los mensajes en inglés, sea cual sea la configuración regional."""
    monkeypatch.setenv("PDDLDOMAINS_LANG", "en")


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    """El catálogo del repositorio."""
    return Catalog()


@pytest.fixture(scope="session")
def analyses(catalog: Catalog) -> dict[str, CollectionAnalysis]:
    """El análisis de todo el catálogo (sin caché, para no depender de ella)."""
    return Analyzer(catalog, cache_file=None).analyze_all()


@pytest.fixture
def write(tmp_path: Path) -> Writer:
    """Escribe un fichero PDDL en un directorio temporal y devuelve su ruta."""

    def writer(name: str, text: str) -> Path:
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path

    return writer
