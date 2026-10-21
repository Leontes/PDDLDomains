"""VAL: lectura del veredicto y validación de los planes de referencia."""

from pathlib import Path

import pytest

from pddldomains.catalog import Catalog
from pddldomains.val import find_tool, parse_check, parse_output, validate

requires_val = pytest.mark.skipif(find_tool("Validate") is None, reason="VAL no está compilado")


def test_parse_valid() -> None:
    result = parse_output(
        "Checking plan: p.plan\nPlan executed successfully\nPlan valid\nFinal value: 12\n", 0
    )
    assert result.verdict == "valid" and result.value == 12


def test_parse_bad_plan_file_is_an_error_not_invalid() -> None:
    # VAL sale con 0 cuando no puede leer el plan (también si no existe).
    assert parse_output("Bad plan file!\n", 0).verdict == "error"


def test_parse_invalid() -> None:
    output = "Plan failed because of unsatisfied precondition\nGoal not satisfied\nPlan invalid\n"
    result = parse_output(output, 1)
    assert result.verdict == "invalid"
    assert result.message.startswith("Goal not satisfied")


def test_parse_crashes() -> None:
    assert parse_output("", 139).verdict == "error"
    assert (
        parse_output("terminate called after throwing an instance of 'std::bad_alloc'", 255).verdict
        == "error"
    )


@requires_val
def test_reference_plans_are_valid(catalog: Catalog) -> None:
    tasks = [t for c in catalog for t in c.tasks if t.plan is not None]
    assert len(tasks) >= 100
    for task in tasks[::10]:  # una muestra: todos tardarían demasiado
        assert task.plan is not None
        result = validate(task.domain, task.problem, task.plan)
        assert result.valid, f"{task.id}: {result.message}"


@requires_val
def test_truncated_plan_is_invalid(catalog: Catalog, tmp_path: Path) -> None:
    task = catalog.find_task("ipc-2023-classical/folding/p01")
    assert task.plan is not None
    truncated = tmp_path / "p01.plan"
    truncated.write_text("".join(task.plan.read_text().splitlines(keepends=True)[:2]))
    assert validate(task.domain, task.problem, truncated).verdict == "invalid"
    assert validate(task.domain, task.problem, tmp_path / "no-existe.plan").verdict == "error"


@pytest.mark.skipif(find_tool("Parser") is None, reason="VAL no está compilado")
def test_parser(catalog: Catalog) -> None:
    task = catalog.find_task("ipc-1998/gripper-round-1-strips/p01")
    result = parse_check(task.domain, task.problem)
    assert result.ok and result.errors == 0
