"""El catálogo: estructura, fichas, análisis e índice."""

import pytest

from pddldomains.analysis import CollectionAnalysis
from pddldomains.catalog import Catalog, CatalogError
from pddldomains.features import TAGS
from pddldomains.index import INDEX_FILES, render_index


def test_every_collection_has_a_complete_card(catalog: Catalog) -> None:
    assert len(catalog) >= 41
    for collection in catalog:
        info = collection.info
        assert info.get("title"), collection.id
        assert info.get("description"), collection.id
        assert info.get("origin", {}).get("source"), collection.id
        for errata in info.get("errata", []):
            assert errata["kind"] in ("requirements", "other"), collection.id
            assert errata["files"] and errata["description"], collection.id
        assert collection.tasks, collection.id


def test_every_task_has_its_domain(catalog: Catalog) -> None:
    for collection in catalog:
        for task in collection.tasks:
            assert task.domain.exists(), task.id
            assert task.problem.exists(), task.id


def test_per_problem_domains(catalog: Catalog) -> None:
    openstacks = catalog.find("openstacks-sequential-satisficing")
    assert len(openstacks.domain_files()) == 20
    assert openstacks.task("p07").domain.name == "domain-p07.pddl"


def test_find(catalog: Catalog) -> None:
    assert catalog.find("trucks-time-constraints").id == "ipc-2006/trucks-time-constraints"
    assert catalog.find_task("ipc-2006/trucks-time-constraints/p03").name == "p03"
    assert catalog.find("zenotravel").id == "ipc-2023-numeric/zenotravel"  # el nombre exacto
    with pytest.raises(CatalogError, match="ambiguous"):
        catalog.find("preferences-complex")
    with pytest.raises(CatalogError):
        catalog.find("no-existe")


def test_analysis(analyses: dict[str, CollectionAnalysis]) -> None:
    for analysis in analyses.values():
        assert analysis.errors == [], analysis.id
        assert set(analysis.tags) <= set(TAGS), analysis.id
        for task in analysis.tasks:
            assert task.undeclared == [], f"{analysis.id}/{task.name}"
    expected = {
        "ipc-1998/gripper-round-1-strips": ["classical", "strips"],
        "ipc-2004/psr-middle-derived-predicates-adl": ["classical", "adl", "derived"],
        "ipc-2004/satellite-time-time-windows-strips": ["numeric", "temporal", "til"],
        "ipc-2006/storage-preferences-qualitative": ["preferences", "constraints"],
        "smtplan/car-nodrag": ["numeric", "pddlplus"],
    }
    for collection_id, tags in expected.items():
        assert analyses[collection_id].tags == tags


#: Dominios de referencia de la escala de niveles (dos o tres por nivel) y su nivel.
REFERENCE_LEVELS = {
    "ipc-2000/blocks-strips-untyped": 1,
    "ipc-1998/gripper-round-1-strips": 1,
    "ipc-2023-classical/rubiks-cube": 2,
    "ipc-2023-classical/slitherlink": 2,
    "ipc-2023-numeric/counters": 3,
    "ipc-2023-numeric/zenotravel": 3,
    "ipc-2002/driverlog-time-simple-automatic": 3,
    "ipc-2002/zenotravel-time-simple-automatic": 3,
    "propios/greenhouse": 3,
    "ipc-2004/psr-middle-derived-predicates-adl": 4,
    "ipc-2004/satellite-time-time-windows-strips": 4,
    "ipc-2006/storage-preferences-qualitative": 5,
    "ipc-2006/trucks-time-constraints": 5,
    "smtplan/car-nodrag": 6,
    "smtplan/generator-events": 6,
}


def test_reference_levels(analyses: dict[str, CollectionAnalysis]) -> None:
    """El nivel calculado de los dominios de referencia es el suyo."""
    for collection_id, level in REFERENCE_LEVELS.items():
        assert analyses[collection_id].level == level, collection_id


def test_index_is_up_to_date(catalog: Catalog, analyses: dict[str, CollectionAnalysis]) -> None:
    for lang, name in INDEX_FILES.items():
        path = catalog.root / name
        assert path.read_text(encoding="utf-8") == render_index(catalog, analyses, lang), (
            f"dominios/{name} is out of date: run 'pddldomains index'"
        )
