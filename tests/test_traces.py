"""Trazas de plan: estados, degradación reproducible, procedencia y comparación con VAL."""

import io
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import Writer
from test_simulator import (
    ADL,
    ADL_PROBLEM,
    BLOCKS,
    BLOCKS_PROBLEM,
    NUMERIC,
    NUMERIC_PROBLEM,
)

from pddldomains.catalog import Catalog, Task
from pddldomains.cli import main
from pddldomains.pddl import read_domain, read_problem, read_text
from pddldomains.simulator import State
from pddldomains.traces import (
    Degradation,
    Provenance,
    TraceError,
    atom_universe,
    build_trace,
    execute,
    generate_trace,
    parse_plan,
    write_trace,
)
from pddldomains.val import find_tool

requires_val = pytest.mark.skipif(find_tool("Validate") is None, reason="VAL no está compilado")

BLOCKS_PLAN = "(pick-up b)\n(stack b c)\n(pick-up a)\n(stack a b)\n"


def trace_of(
    domain: str, problem: str, plan: str, degradation: Degradation | None = None, **options: Any
) -> dict[str, Any]:
    execution = execute(read_domain(domain), read_problem(problem), parse_plan(plan))
    return build_trace(execution, degradation or Degradation(), **options)


def observed(trace: dict[str, Any]) -> list[dict[str, Any]]:
    return [state for state in trace["states"] if not state.get("missing")]


# --- Planes -------------------------------------------------------------------------------


def test_parse_plan() -> None:
    steps = parse_plan("; comentario\n(Pick-Up a)\n\n(stack a b) ; cost 1\n(handempty-noop)\n")
    assert [(s.name, s.arguments) for s in steps] == [
        ("pick-up", ("a",)),
        ("stack", ("a", "b")),
        ("handempty-noop", ()),
    ]
    timed = parse_plan("0.000: (pick-up a) [1.000]\n1.5: (stack a b)\n")
    assert [(s.time, s.duration) for s in timed] == [(0.0, 1.0), (1.5, None)]


@pytest.mark.parametrize("text", ["pick-up a\n", "(pick-up a\n", "()\n", "0: (a) [x]\n"])
def test_bad_plan_lines(text: str) -> None:
    with pytest.raises(TraceError, match="plan line 1"):
        parse_plan(text)


def test_inapplicable_action_names_the_condition() -> None:
    plan = "(pick-up b)\n(pick-up a)\n"
    with pytest.raises(TraceError, match=r"plan action 2, \(pick-up a\).*\(handempty\)"):
        execute(read_domain(BLOCKS), read_problem(BLOCKS_PROBLEM), parse_plan(plan))


def test_mixed_timestamps() -> None:
    with pytest.raises(TraceError, match="mixes"):
        execute(
            read_domain(BLOCKS),
            read_problem(BLOCKS_PROBLEM),
            parse_plan("0: (pick-up b)\n(stack b c)\n"),
        )


# --- Estados ------------------------------------------------------------------------------


def test_complete_trace() -> None:
    trace = trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN)
    assert trace["execution"]["goal_reached"]
    assert trace["world"] == "closed"
    assert trace["objects"] == {"a": "block", "b": "block", "c": "block"}
    assert [a["name"] for a in trace["actions"]] == ["pick-up", "stack", "pick-up", "stack"]
    assert trace["actions"][1] == {"step": 2, "time": 2, "name": "stack", "arguments": ["b", "c"]}
    states = trace["states"]
    assert [s["step"] for s in states] == [0, 1, 2, 3, 4]
    assert [s["time"] for s in states] == [0, 1, 2, 3, 4]
    assert states[0]["true"] == [
        "(clear a)",
        "(clear b)",
        "(clear c)",
        "(handempty)",
        "(ontable a)",
        "(ontable b)",
        "(ontable c)",
    ]
    assert "(on a b)" in states[-1]["true"] and "(handempty)" in states[-1]["true"]
    assert all(s["unknown"] == [] and "false" not in s for s in states)


def test_open_world_lists_the_universe() -> None:
    trace = trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, Degradation(missing=25), world="open")
    for state in trace["states"]:
        listed = state["true"] + state["false"] + state["unknown"]
        assert len(listed) == len(set(listed)) == trace["universe"]["size"]


def test_goal_not_reached() -> None:
    trace = trace_of(BLOCKS, BLOCKS_PROBLEM, "(pick-up b)\n")
    assert trace["execution"]["goal_reached"] is False


def test_timestamped_plan() -> None:
    plan = "0.000: (pick-up b) [1.000]\n2.000: (stack b c) [0.5]\n"
    trace = trace_of(BLOCKS, BLOCKS_PROBLEM, plan)
    assert [a["time"] for a in trace["actions"]] == [0, 2]
    assert [s["time"] for s in trace["states"]] == [0, 1, 2.5]


def test_numeric_values() -> None:
    trace = trace_of(NUMERIC, NUMERIC_PROBLEM, "(pour t1 t2)\n(double t2)\n")
    values = [state["values"] for state in trace["states"]]
    assert values[0]["(capacity t1)"] == 10  # constantes incluidas
    assert values[1]["(level t2)"] == 4 and values[1]["(total-cost)"] == 2.5
    assert values[2]["(level t2)"] == 8 and values[2]["(spare)"] == 1


def test_dynamic_and_typed_universes() -> None:
    domain = BLOCKS.replace("(holding ?x - block))", "(holding ?x - block) (heavy ?x - block))")
    problem = BLOCKS_PROBLEM.replace("(handempty))", "(handempty) (heavy a))")
    sim_execution = execute(read_domain(domain), read_problem(problem), parse_plan(BLOCKS_PLAN))
    dynamic = atom_universe(sim_execution.simulator, sim_execution.states, "dynamic")
    typed = atom_universe(sim_execution.simulator, sim_execution.states, "typed")
    # heavy es estático: en dynamic solo está el cierto al principio.
    assert [a for a in dynamic if a[0] == "heavy"] == [("heavy", "a")]
    assert [a for a in typed if a[0] == "heavy"] == [("heavy", "a"), ("heavy", "b"), ("heavy", "c")]
    assert len(typed) == len(dynamic) + 2 == 3 * 3 + 3 * 4 + 1  # on, 4 de un bloque, handempty


def test_max_atoms() -> None:
    with pytest.raises(TraceError, match="possible atoms"):
        trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, max_atoms=10)


# --- Degradación --------------------------------------------------------------------------


def test_exact_counts() -> None:
    degradation = Degradation(missing=30, noise=10, seed=3)
    trace = trace_of(ADL, ADL_PROBLEM, "(empty-box b1 b2)\n(toggle i1)\n", degradation)
    size = trace["universe"]["size"]
    hidden = math.floor(size * 0.3 + 0.5)
    for state in trace["states"]:
        assert len(state["unknown"]) == hidden
    flipped = math.floor((size - hidden) * 0.1 + 0.5)
    counts = trace["degradation"]
    assert counts["hidden_atoms"] == hidden * 3
    assert counts["flipped_atoms"] == flipped * 3


def test_noise_flips_observed_atoms() -> None:
    clean = trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, world="open")
    noisy = trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, Degradation(noise=20), world="open")
    size = clean["universe"]["size"]
    for before, after in zip(clean["states"], noisy["states"], strict=True):
        changed = set(before["true"]) ^ set(after["true"])
        assert len(changed) == math.floor(size * 0.2 + 0.5)
        assert after["unknown"] == []


def hidden_sets(trace: dict[str, Any]) -> list[set[str]]:
    return [set(state["unknown"]) for state in trace["states"]]


def test_reproducible_and_nested() -> None:
    def run(**values: float) -> dict[str, Any]:
        return trace_of(ADL, ADL_PROBLEM, "(empty-box b1 b2)\n", Degradation(seed=5, **values))

    assert run(missing=40, noise=10) == run(missing=40, noise=10)
    assert hidden_sets(run(missing=40)) != hidden_sets(
        trace_of(ADL, ADL_PROBLEM, "(empty-box b1 b2)\n", Degradation(seed=6, missing=40))
    )
    for less, more in zip(hidden_sets(run(missing=20)), hidden_sets(run(missing=50)), strict=True):
        assert less < more
    # El ruido también está anidado (con los mismos huecos).
    base = trace_of(ADL, ADL_PROBLEM, "(empty-box b1 b2)\n", world="open")

    def flips(noise: float) -> list[set[str]]:
        trace = trace_of(
            ADL, ADL_PROBLEM, "(empty-box b1 b2)\n", Degradation(seed=5, noise=noise), world="open"
        )
        return [
            set(a["true"]) ^ set(b["true"])
            for a, b in zip(base["states"], trace["states"], strict=True)
        ]

    for less, more in zip(flips(10), flips(30), strict=True):
        assert less <= more


def test_missing_states() -> None:
    plan = "(toggle i1)\n" * 9
    trace = trace_of(ADL, ADL_PROBLEM, plan, Degradation(missing_states=30, seed=1))
    missing = [s["step"] for s in trace["states"] if s.get("missing")]
    assert len(missing) == 3 and missing == trace["degradation"]["missing_states"]
    assert all(set(s) == {"step", "time", "missing"} for s in trace["states"] if s.get("missing"))
    assert len(trace["actions"]) == 9  # las acciones no se degradan
    more = trace_of(ADL, ADL_PROBLEM, plan, Degradation(missing_states=60, seed=1))
    assert set(missing) < set(more["degradation"]["missing_states"])


def test_numeric_degradation() -> None:
    plan = "(pour t1 t2)\n(double t2)\n"
    clean = trace_of(NUMERIC, NUMERIC_PROBLEM, plan)
    trace = trace_of(NUMERIC, NUMERIC_PROBLEM, plan, Degradation(missing=50, noise=100, seed=2))
    for before, after in zip(clean["states"], trace["states"], strict=True):
        assert len(after["unknown_values"]) == 3  # 50 % de 6
        assert set(after["values"]) | set(after["unknown_values"]) == set(before["values"])
        for term, value in after["values"].items():
            original = before["values"][term]
            assert value != original
            assert abs(value - original) <= 0.1 * (abs(original) or 1)


def test_bad_degradation() -> None:
    with pytest.raises(TraceError, match="missing must be between 0 and 100"):
        trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, Degradation(missing=120))
    with pytest.raises(TraceError, match="world must be"):
        trace_of(BLOCKS, BLOCKS_PROBLEM, BLOCKS_PLAN, world="half-open")


# --- Procedencia, JSON y CLI --------------------------------------------------------------


def reference_task(catalog: Catalog, collection: str = "rubiks-cube") -> Task:
    task = catalog.find(collection).tasks[0]
    assert task.plan is not None
    return task


def test_provenance(catalog: Catalog) -> None:
    task = reference_task(catalog)
    assert task.plan is not None
    trace = generate_trace(
        task.domain,
        task.problem,
        task.plan,
        provenance=Provenance("lama", "--alias lama-first", 7),
        degradation=Degradation(missing=10, seed=9),
        catalog=catalog,
    )
    assert trace["format"] == "pddldomains-trace" and trace["version"] == 1
    assert trace["collection"] == "ipc-2023-classical/rubiks-cube"
    assert trace["domain"]["name"] == "rubiks-cube"
    assert trace["domain"]["file"] == "ipc-2023-classical/rubiks-cube/domain.pddl"
    assert trace["problem"]["id"] == "p01"
    assert re.fullmatch(r"[0-9a-f]{64}", trace["plan"]["sha256"])
    assert (trace["plan"]["planner"], trace["plan"]["config"], trace["plan"]["seed"]) == (
        "lama",
        "--alias lama-first",
        7,
    )
    assert trace["degradation"]["seed"] == 9 and trace["degradation"]["missing_percent"] == 10


def test_provenance_outside_the_catalog(write: Writer) -> None:
    domain = write("domain.pddl", BLOCKS)
    problem = write("problem.pddl", BLOCKS_PROBLEM)
    plan = write("plan.txt", BLOCKS_PLAN)
    trace = generate_trace(domain, problem, plan)
    assert trace["collection"] is None and "id" not in trace["problem"]
    assert trace["problem"]["file"] == str(problem)


@pytest.mark.parametrize("compact", [False, True])
def test_write_trace(compact: bool) -> None:
    trace = trace_of(NUMERIC, NUMERIC_PROBLEM, "(pour t1 t2)\n", Degradation(missing=20))
    stream = io.StringIO()
    write_trace(trace, stream, compact=compact)
    text = stream.getvalue()
    assert json.loads(text) == trace
    assert (text.count("\n") == 1) == compact


def test_cli(catalog: Catalog, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "traza.json"
    arguments = ["trace", "--task", "rubiks-cube/p02", "--missing", "20", "--seed", "4"]
    assert main([*arguments, "-o", str(output), "--planner", "lama"]) == 0
    trace = json.loads(output.read_text(encoding="utf-8"))
    assert trace["problem"]["id"] == "p02" and trace["plan"]["planner"] == "lama"
    assert main([*arguments, "--compact"]) == 0
    assert json.loads(capsys.readouterr().out)["states"] == trace["states"]


def test_cli_errors(write: Writer, capsys: pytest.CaptureFixture[str]) -> None:
    domain = write("domain.pddl", BLOCKS)
    problem = write("problem.pddl", BLOCKS_PROBLEM)
    bad = write("bad.plan", "(stack a b)\n")
    assert main(["trace", str(domain), str(problem), str(bad)]) == 2
    assert "is not applicable" in capsys.readouterr().err
    short = write("short.plan", "(pick-up a)\n")
    assert main(["trace", str(domain), str(problem), str(short)]) == 1
    assert "does not reach the goal" in capsys.readouterr().err
    assert main(["trace", str(domain), str(problem)]) == 2
    with pytest.raises(SystemExit):
        main(["trace", str(domain), str(problem), str(short), "--missing", "150"])


# --- Comparación con VAL ------------------------------------------------------------------


def val_states(task_files: tuple[Path, Path, Path], initial: State) -> list[State]:
    """Los estados que deja cada acción según VAL (``Validate -v``: Adding/Deleting/Updating)."""
    validate = find_tool("Validate")
    assert validate is not None
    output = subprocess.run(
        [str(validate), "-v", *map(str, task_files)],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    ).stdout
    atoms, values = set(initial.atoms), dict(initial.values)
    states = []
    for block in re.split(r"Checking next happening \(time [^)]*\)\n", output)[1:]:
        adds, deletes = set(), set()
        for line in block.splitlines():
            words = tuple(line.split(" ", 1)[-1].strip("() ").lower().split())
            if line.startswith("Adding "):
                adds.add(words)
            elif line.startswith("Deleting "):
                deletes.add(words)
            elif match := re.match(r"Updating \((.*?)\) \(\S+\) by (\S+) (.+)$", line):
                term, amount, operation = tuple(match[1].split()), float(match[2]), match[3]
                current = values.get(term, 0.0)
                values[term] = {
                    "assignment": amount,
                    "increase": current + amount,
                    "decrease": current - amount,
                    "scale up": current * amount,
                    "scale down": current / amount if amount else math.nan,
                }[operation]
        atoms = (atoms - deletes) | adds
        states.append(State(frozenset(atoms), frozenset(), dict(values)))
    return states


def same_states(files: tuple[Path, Path, Path]) -> None:
    domain, problem, plan = files
    execution = execute(
        read_domain(read_text(domain)),
        read_problem(read_text(problem)),
        parse_plan(plan.read_text(encoding="utf-8")),
    )
    expected = val_states(files, execution.states[0])
    assert len(expected) == len(execution.steps)
    for step, (theirs, ours) in enumerate(zip(expected, execution.states[1:], strict=True), 1):
        assert ours.atoms == theirs.atoms, f"{plan} paso {step}"
        assert ours.values.keys() == theirs.values.keys(), f"{plan} paso {step}"
        for term, value in ours.values.items():
            assert math.isclose(value, theirs.values[term], rel_tol=1e-4, abs_tol=1e-4), term


@requires_val
@pytest.mark.parametrize(
    "collection", ["folding", "labyrinth", "recharging-robots", "ricochet-robots", "rubiks-cube"]
)
def test_same_states_as_val(catalog: Catalog, collection: str) -> None:
    """Los estados de los planes de referencia coinciden con los de VAL, paso a paso."""
    for task in catalog.find(collection).tasks[:4]:
        assert task.plan is not None
        same_states((task.domain, task.problem, task.plan))


#: Planes aleatorios (generados enumerando las acciones aplicables) de dominios numéricos y
#: con predicados derivados.
OTHER_PLANS = {
    "counters/p01": ["(decrement c0)"] * 6 + ["(decrement c1)"] * 3 + ["(increment c3)"] * 3,
    "ipc-2023-numeric/zenotravel/p01": [
        "(board person1 plane1 city0)",
        "(refuel plane1)",
        "(fly-slow plane1 city0 city0)",
        "(debark person1 plane1 city0)",
        "(board person1 plane1 city0)",
        "(fly-slow plane1 city0 city2)",
        "(fly-fast plane1 city2 city2)",
        "(debark person1 plane1 city2)",
    ],
    "psr-middle-derived-predicates-adl/p02": [
        "(wait)",
        "(open sd7)",
        "(close sd4)",
        "(open sd2)",
        "(open sd8)",
        "(close sd7)",
        "(open sd1)",
        "(close cb2)",
        "(open sd3)",
        "(close sd8)",
        "(wait)",
        "(close cb1)",
    ],
}


@requires_val
@pytest.mark.parametrize("task_id", sorted(OTHER_PLANS))
def test_same_states_as_val_numeric_and_derived(
    catalog: Catalog, task_id: str, write: Writer
) -> None:
    task = catalog.find_task(task_id)
    plan = write("plan.txt", "\n".join(OTHER_PLANS[task_id]) + "\n")
    same_states((task.domain, task.problem, plan))
