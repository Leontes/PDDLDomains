"""Ficheros originales: patrones de origen y, si están los clones, las erratas.

Las comprobaciones contra los repositorios de origen necesitan sus clones en
``tools/fuentes/`` (los crea ``pddldomains sources check``, que necesita red); sin ellos se
saltan.
"""

from pathlib import Path

import pytest

from pddldomains.catalog import Catalog, read_collection
from pddldomains.lint import lint_domain, lint_problem
from pddldomains.sources import SOURCES_DIR, Origin, _open, _origin_files, compare, problem_number

requires_sources = pytest.mark.skipif(
    not (SOURCES_DIR / "potassco__pddl-instances").exists(),
    reason="sin clones de los repositorios de origen (pddldomains sources check)",
)


def test_origin_patterns() -> None:
    origin = Origin("u", "c", "ipc/x", "domains/domain-{n}.pddl", "instances/instance-{n}.pddl")
    assert origin.per_problem_domain
    assert origin.file(origin.problems, 7) == "ipc/x/instances/instance-7.pddl"
    assert (
        Origin("u", "c", "b", "d.pddl", "prob{nn}.pddl").file("prob{nn}.pddl", 3) == "b/prob03.pddl"
    )
    assert problem_number("p07") == 7 and problem_number("x") is None


def test_every_origin_is_complete(catalog: Catalog) -> None:
    for collection in catalog:
        origin = collection.info.get("origin", {})
        if "repository" in origin:
            assert Origin.from_info(collection.info) is not None, collection.id
        else:
            assert collection.origin == "propios", collection.id


@requires_sources
def test_every_difference_is_documented(catalog: Catalog) -> None:
    for collection in catalog:
        if Origin.from_info(collection.info) is None:
            continue
        for result in compare(collection):
            assert result.status != "missing", f"{collection.id}/{result.name}"
            assert result.documented, f"{collection.id}/{result.name} sin documentar"


@requires_sources
@pytest.mark.parametrize(
    ("collection_id", "code"),
    [
        ("ipc-2011/floor-tile-sequential-satisficing", "undeclared-requirement"),
        ("ipc-2006/tpp-preferences-complex", "glued-dash"),
        ("ipc-2006/pathways-preferences-complex", "repeated-value"),
        ("ipc-2011/woodworking-sequential-satisficing", "type-without-names"),
        ("smtplan/car-nodrag", "function-without-parentheses"),
        ("smtplan/generator-events", "uninitialized-function"),
        ("smtplan/generator-nonlinear", "domain-mismatch"),
        ("ipc-2004/satellite-time-time-windows-strips", "shared-name"),
    ],
)
def test_lint_finds_the_errata_in_the_originals(
    catalog: Catalog, collection_id: str, code: str, tmp_path: Path
) -> None:
    """La revisión encuentra en los ficheros originales cada errata que se corrigió a mano."""
    collection = catalog.find(collection_id)
    origin = Origin.from_info(collection.info)
    assert origin is not None
    repo = _open(origin)
    for name, _, remote in _origin_files(collection, origin):
        content = repo.read(origin.commit, remote)
        assert content is not None
        (tmp_path / name).write_bytes(content)
    original = read_collection(tmp_path, collection_id)
    codes = set()
    for domain_path in original.domain_files():
        domain, findings = lint_domain(domain_path)
        codes |= {f.code for f in findings}
        for task in original.tasks:
            if task.domain == domain_path and domain is not None:
                codes |= {f.code for f in lint_problem(task.problem, domain)}
    assert code in codes
