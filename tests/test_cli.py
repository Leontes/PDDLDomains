"""La línea de comandos."""

import json
from pathlib import Path

import pytest

from pddldomains.cli import main, parse_numbers


def test_list_and_types(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list", "--type", "pddlplus", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {d["id"] for d in data} == {"smtplan/car-nodrag", "smtplan/generator-events"}
    assert main(["types"]) == 0
    assert "pddlplus" in capsys.readouterr().out


def test_info(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", "floor-tile-sequential-satisficing"]) == 0
    out = capsys.readouterr().out
    assert "Erratum (*)" in out and "p20" in out
    assert "Level: 3 (PDDL 2.1) because of :action-costs" in out


def test_levels(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["levels"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith("1 STRIPS") and lines[6].startswith("6 PDDL+")
    assert main(["list", "--max-level", "1", "--format", "ids"]) == 0
    assert capsys.readouterr().out.split() == [
        "ipc-1998/gripper-round-1-strips",
        "ipc-2000/blocks-strips-untyped",
    ]


def test_dataset_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["dataset", "smoke-test", "--relative", "--type", "pddlplus"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2  # el problema más pequeño de cada colección PDDL+
    assert lines[0].startswith("smtplan/car-nodrag/domain.pddl smtplan/car-nodrag/p")
    assert lines[1].startswith("smtplan/generator-events/domain.pddl smtplan/generator-events/p")


def test_dataset_export(tmp_path: Path) -> None:
    assert (
        main(
            [
                "dataset",
                "--collection",
                "ipc-1998/*",
                "--per-collection",
                "3",
                "--export",
                str(tmp_path / "x"),
            ]
        )
        == 0
    )
    assert len(list((tmp_path / "x" / "ipc-1998" / "gripper-round-1-strips").glob("p*.pddl"))) == 3


def test_lint_exit_codes(tmp_path: Path) -> None:
    assert main(["lint", "ipc-2006/trucks-time-constraints"]) == 0
    broken = tmp_path / "domain.pddl"
    broken.write_text(
        "(define (domain d) (:predicates (p))"
        " (:action a :parameters () :precondition (q) :effect (p)))"
    )
    assert main(["lint", str(broken)]) == 1


def test_unknown_collection() -> None:
    assert main(["info", "no-existe"]) == 2


def test_parse_numbers() -> None:
    assert parse_numbers("1-3,7") == [1, 2, 3, 7]
