"""Generadores: parámetros, problemas que pasan la revisión y planes válidos."""

import random
import re
from pathlib import Path

import pytest

from pddldomains.catalog import Catalog
from pddldomains.cli import main
from pddldomains.generators import GENERATORS, GeneratorError, find_generator
from pddldomains.generators.base import Param, ensure_total_cost, rename_tokens, set_problem_name
from pddldomains.generators.own import OWN_GENERATORS
from pddldomains.generators.parking import perl_problem
from pddldomains.lint import lint_domain, lint_problem
from pddldomains.val import find_tool, validate


def test_param_values() -> None:
    rng = random.Random(1)
    count = Param("n", int, 3, "", minimum=1)
    assert count.resolve("5", rng) == 5
    assert 2 <= count.resolve("2..4", rng) <= 4
    with pytest.raises(GeneratorError):
        count.resolve("0", rng)
    with pytest.raises(GeneratorError):
        count.resolve("x", rng)
    with pytest.raises(GeneratorError):
        Param("m", str, "a", "", choices=("a", "b")).resolve("c", rng)


def test_text_helpers() -> None:
    text = "(define (problem x) (:domain d) (:init (arm-empty) (on-table a)) (:goal (on-table a)))"
    renamed = rename_tokens(text, {"arm-empty": "handempty", "on-table": "ontable"})
    assert "(handempty)" in renamed and "(ontable a)" in renamed
    assert "(problem nuevo)" in set_problem_name(text, "nuevo")
    with_cost = ensure_total_cost(text)
    assert "(= (total-cost) 0)" in with_cost and "(:metric minimize (total-cost))" in with_cost
    assert ensure_total_cost(with_cost) == with_cost


PARKING_REFERENCES = sorted((Path(__file__).parent / "datos" / "parking").glob("*.pddl"))


@pytest.mark.parametrize("reference", PARKING_REFERENCES, ids=lambda p: p.stem)
def test_parking_port_matches_the_perl_original(reference: Path) -> None:
    """Las referencias son la salida de ``parking-generator.pl problem <c> <n> seq <s>``."""
    match = re.fullmatch(r"curbs(\d+)-cars(\d+)-seed(\d+)", reference.stem)
    assert match is not None
    curbs, cars, seed = (int(g) for g in match.groups())
    assert perl_problem(curbs, cars, seed) == reference.read_text()


def test_parking_rejects_too_many_cars(tmp_path: Path) -> None:
    arguments = ["generate", "parking", "-p", "curbs=3", "-p", "cars=5", "-o", str(tmp_path)]
    assert main(arguments) == 2


def test_find_generator(catalog: Catalog) -> None:
    assert find_generator("counters", catalog).name == "counters"
    assert find_generator("smtplan/car-nodrag", catalog).name == "car"
    with pytest.raises(GeneratorError, match="random-walk"):
        find_generator("ipc-2011/sokoban-sequential-satisficing", catalog)


def check_output(directory: Path) -> None:
    domain_path = directory / "domain.pddl"
    domain, findings = lint_domain(domain_path)
    assert domain is not None
    for problem in sorted(directory.glob("p*.pddl")):
        errors = [f for f in lint_problem(problem, domain) if f.level != "info"]
        assert errors == [], [f.format(directory) for f in errors]


#: Los generadores que no necesitan nada de tools/ (salvo el paseo, que se prueba aparte).
BUILTIN = [g.name for g in OWN_GENERATORS] + ["parking"]


@pytest.mark.parametrize("generator", BUILTIN)
def test_own_generators(generator: str, tmp_path: Path) -> None:
    assert main(["generate", generator, "-n", "3", "-o", str(tmp_path), "--no-check"]) == 0
    assert len(list(tmp_path.glob("p*.pddl"))) == 3
    check_output(tmp_path)


def test_generation_is_reproducible(tmp_path: Path) -> None:
    for name in ("a", "b"):
        assert (
            main(
                [
                    "generate",
                    "counters",
                    "-n",
                    "2",
                    "-s",
                    "9",
                    "-o",
                    str(tmp_path / name),
                    "--no-check",
                ]
            )
            == 0
        )
    for problem in ("p01.pddl", "p02.pddl"):
        assert (tmp_path / "a" / problem).read_text() == (tmp_path / "b" / problem).read_text()


def test_series(tmp_path: Path) -> None:
    assert (
        main(
            [
                "generate",
                "counters",
                "-p",
                "counters=3,5",
                "-n",
                "2",
                "-o",
                str(tmp_path),
                "--no-check",
            ]
        )
        == 0
    )
    assert sorted(p.name for p in tmp_path.glob("p*.pddl")) == [
        "p01.pddl",
        "p02.pddl",
        "p03.pddl",
        "p04.pddl",
    ]
    assert "c4" in (tmp_path / "p03.pddl").read_text()


def test_unsolvable_parameters_are_rejected(tmp_path: Path) -> None:
    assert main(["generate", "car", "-p", "limit=1", "-p", "max-time=5", "-o", str(tmp_path)]) == 2
    assert (
        main(["generate", "counters", "-p", "counters=6", "-p", "max-int=3", "-o", str(tmp_path)])
        == 2
    )


@pytest.mark.parametrize(
    "collection",
    [
        "ipc-1998/gripper-round-1-strips",
        "ipc-2011/tidybot-sequential-satisficing",
        "ipc-2023-classical/rubiks-cube",
        "ipc-2023-classical/slitherlink",
    ],
)
@pytest.mark.parametrize("mode", ["goal", "both"])
def test_random_walk(collection: str, mode: str, tmp_path: Path) -> None:
    """El paseo es un plan: si VAL está compilado, tiene que ser válido."""
    arguments = ["generate", "random-walk", "-p", f"collection={collection}", "-p", f"mode={mode}"]
    assert main([*arguments, "-n", "2", "-o", str(tmp_path), "--no-check"]) == 0
    check_output(tmp_path)
    if find_tool("Validate") is None:
        pytest.skip("VAL no está compilado")
    for problem in sorted(tmp_path.glob("p*.pddl")):
        result = validate(tmp_path / "domain.pddl", problem, problem.with_suffix(".plan"))
        assert result.valid, result.message


def test_random_walk_rejects_non_classical(tmp_path: Path) -> None:
    arguments = [
        "generate",
        "random-walk",
        "-p",
        "collection=smtplan/car-nodrag",
        "-o",
        str(tmp_path),
    ]
    assert main(arguments) == 2


EXTERNAL = [g.name for g in GENERATORS.values() if g.origin not in ("own", "ported")]


@pytest.mark.parametrize("generator", EXTERNAL)
def test_external_generators(generator: str, tmp_path: Path) -> None:
    reason = GENERATORS[generator].unavailable()
    if reason:
        pytest.skip(reason)
    assert main(["generate", generator, "-n", "2", "-o", str(tmp_path), "--no-check"]) == 0
    check_output(tmp_path)
    if find_tool("Validate") is not None:
        for plan in sorted(tmp_path.glob("p*.plan")):
            result = validate(tmp_path / "domain.pddl", plan.with_suffix(".pddl"), plan)
            assert result.valid, result.message
