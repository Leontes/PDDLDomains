"""El simulador: estados, precondiciones y efectos (STRIPS, ADL, derivados y numéricos)."""

import pytest

from pddldomains.pddl import read_domain, read_problem
from pddldomains.sexpr import to_text
from pddldomains.simulator import SimulationError, Simulator, State, Unsupported, atom_text

BLOCKS = """
(define (domain blocks)
  (:requirements :strips :typing)
  (:types block)
  (:predicates (on ?x ?y - block) (ontable ?x - block) (clear ?x - block) (handempty)
               (holding ?x - block))
  (:action pick-up
    :parameters (?x - block)
    :precondition (and (clear ?x) (ontable ?x) (handempty))
    :effect (and (not (ontable ?x)) (not (clear ?x)) (not (handempty)) (holding ?x)))
  (:action stack
    :parameters (?x ?y - block)
    :precondition (and (holding ?x) (clear ?y))
    :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (handempty) (on ?x ?y))))
"""

BLOCKS_PROBLEM = """
(define (problem tres)
  (:domain blocks)
  (:objects a b c - block)
  (:init (ontable a) (ontable b) (ontable c) (clear a) (clear b) (clear c) (handempty))
  (:goal (and (on a b) (on b c))))
"""


def simulator(domain: str, problem: str) -> Simulator:
    return Simulator(read_domain(domain), read_problem(problem))


def run(sim: Simulator, *actions: str, state: State | None = None) -> State:
    """Aplica las acciones (``"stack a b"``), comprobando que son aplicables."""
    state = state or sim.initial_state()
    for text in actions:
        name, *arguments = text.split()
        operator, binding = sim.action(name, arguments)
        assert sim.applicable(operator, binding, state), text
        state = sim.successor(operator, binding, state)
    return state


def atoms(state: State) -> set[str]:
    return {atom_text(atom) for atom in state.facts}


def test_strips() -> None:
    sim = simulator(BLOCKS, BLOCKS_PROBLEM)
    state = run(sim, "pick-up b", "stack b c", "pick-up a", "stack a b")
    assert {"(on a b)", "(on b c)", "(clear a)", "(handempty)"} <= atoms(state)
    assert "(clear b)" not in atoms(state)
    assert sim.problem.goal is not None and sim.holds(sim.problem.goal, {}, state)


def test_unsatisfied_precondition() -> None:
    sim = simulator(BLOCKS, BLOCKS_PROBLEM)
    state = run(sim, "pick-up a")
    operator, binding = sim.action("pick-up", ["b"])
    assert not sim.applicable(operator, binding, state)
    failing = sim.unsatisfied(operator, binding, state)
    assert failing is not None and to_text(failing) == "(handempty)"


@pytest.mark.parametrize(
    ("action", "message"),
    [
        ("fly a", "unknown action 'fly'"),
        ("stack a", "'stack' has 2 parameters and is given 1"),
        ("pick-up d", "unknown object 'd' in 'pick-up'"),
    ],
)
def test_bad_actions(action: str, message: str) -> None:
    sim = simulator(BLOCKS, BLOCKS_PROBLEM)
    name, *arguments = action.split()
    with pytest.raises(SimulationError, match=message):
        sim.action(name, arguments)


def test_argument_types() -> None:
    domain = BLOCKS.replace("(:types block)", "(:types block table)")
    problem = BLOCKS_PROBLEM.replace("a b c - block", "a b c - block t - table")
    with pytest.raises(SimulationError, match="'t' is not of type block"):
        simulator(domain, problem).action("pick-up", ["t"])


ADL = """
(define (domain adl)
  (:requirements :adl)
  (:types item box)
  (:predicates (in ?i - item ?b - box) (open ?b - box) (empty ?b - box) (moved ?i - item)
               (seen) (marked ?i - item))
  (:action empty-box
    :parameters (?b ?to - box)
    :precondition (and (not (= ?b ?to)) (open ?b) (exists (?i - item) (in ?i ?b))
                       (imply (open ?to) (not (empty ?to))))
    :effect (and (forall (?i - item)
                   (when (in ?i ?b) (and (not (in ?i ?b)) (in ?i ?to) (moved ?i))))
                 (empty ?b)
                 (when (or (seen) (open ?to)) (seen))))
  (:action toggle
    :parameters (?i - item)
    :precondition (and)
    :effect (and (not (marked ?i)) (marked ?i))))
"""

ADL_PROBLEM = """
(define (problem p)
  (:domain adl)
  (:objects i1 i2 i3 - item b1 b2 - box)
  (:init (in i1 b1) (in i2 b1) (in i3 b2) (open b1) (open b2))
  (:goal (forall (?i - item) (in ?i b2))))
"""


def test_adl() -> None:
    sim = simulator(ADL, ADL_PROBLEM)
    operator, binding = sim.action("empty-box", ["b1", "b1"])
    assert not sim.applicable(operator, binding, sim.initial_state())  # (not (= ?b ?to))
    state = run(sim, "empty-box b1 b2")
    assert {"(in i1 b2)", "(in i2 b2)", "(in i3 b2)", "(moved i1)", "(moved i2)"} <= atoms(state)
    assert "(moved i3)" not in atoms(state)
    assert {"(empty b1)", "(seen)"} <= atoms(state)
    assert sim.problem.goal is not None and sim.holds(sim.problem.goal, {}, state)
    # b1 ya no tiene nada: (exists (?i - item) (in ?i b1)) es falso.
    operator, binding = sim.action("empty-box", ["b1", "b2"])
    assert not sim.applicable(operator, binding, state)


def test_add_wins_over_delete() -> None:
    # Primero se borra y después se añade: (marked i1) queda cierto.
    sim = simulator(ADL, ADL_PROBLEM)
    assert "(marked i1)" in atoms(run(sim, "toggle i1"))


DERIVED = """
(define (domain derived)
  (:requirements :typing :derived-predicates :negative-preconditions)
  (:types node)
  (:predicates (edge ?x ?y - node) (reach ?x ?y - node) (isolated ?x - node) (go ?x - node))
  (:derived (reach ?x - node ?y - node)
     (or (edge ?x ?y) (exists (?z - node) (and (edge ?x ?z) (reach ?z ?y)))))
  (:derived (isolated ?x - node) (not (exists (?y - node) (reach ?x ?y))))
  (:action link
    :parameters (?x ?y - node)
    :precondition (and (not (reach ?x ?y)) (not (= ?x ?y)))
    :effect (edge ?x ?y))
  (:action start
    :parameters (?x - node)
    :precondition (isolated ?x)
    :effect (go ?x)))
"""

DERIVED_PROBLEM = """
(define (problem p)
  (:domain derived)
  (:objects a b c d - node)
  (:init (edge a b) (edge b c))
  (:goal (reach a d)))
"""


def test_derived_predicates() -> None:
    sim = simulator(DERIVED, DERIVED_PROBLEM)
    state = sim.initial_state()
    # Las cabezas llevan tipos: los átomos derivados son (reach a c), no (reach a - node ...).
    assert {"(reach a b)", "(reach a c)", "(reach b c)"} <= atoms(state)
    assert {"(isolated c)", "(isolated d)"} <= atoms(state)  # estrato posterior (negación)
    assert "(isolated a)" not in atoms(state)
    operator, binding = sim.action("link", ["a", "c"])
    assert not sim.applicable(operator, binding, state)
    state = run(sim, "start c", "link c d", state=state)
    assert {"(reach a d)", "(go c)"} <= atoms(state) and "(isolated c)" not in atoms(state)
    assert state.atoms == {("edge", "a", "b"), ("edge", "b", "c"), ("edge", "c", "d"), ("go", "c")}


def test_derived_predicates_must_be_stratifiable() -> None:
    domain = DERIVED.replace(
        "(:derived (isolated ?x - node) (not (exists (?y - node) (reach ?x ?y))))",
        "(:derived (isolated ?x - node) (not (go ?x)))\n"
        "  (:derived (go ?x - node) (not (isolated ?x)))",
    ).replace(":effect (go ?x)", ":effect (edge ?x ?x)")
    with pytest.raises(Unsupported, match="not stratifiable"):
        simulator(domain, DERIVED_PROBLEM)


NUMERIC = """
(define (domain numeric)
  (:requirements :typing :numeric-fluents :action-costs)
  (:types tank)
  (:functions (level ?t - tank) (capacity ?t - tank) (spare) (total-cost) - number)
  (:action pour
    :parameters (?from ?to - tank)
    :precondition (and (> (level ?from) 0)
                       (<= (+ (level ?to) (level ?from)) (capacity ?to)))
    :effect (and (increase (level ?to) (level ?from)) (assign (level ?from) 0)
                 (increase (total-cost) (+ 1 (/ (level ?from) 2)))))
  (:action double
    :parameters (?t - tank)
    :precondition (< (* 2 (level ?t)) (capacity ?t))
    :effect (and (scale-up (level ?t) 2) (decrease (spare) 1)))
  (:action halve
    :parameters (?t - tank)
    :precondition (>= (level ?t) (- (spare) 3))
    :effect (scale-down (level ?t) (spare))))
"""

NUMERIC_PROBLEM = """
(define (problem p)
  (:domain numeric)
  (:objects t1 t2 - tank)
  (:init (= (level t1) 3) (= (level t2) 1) (= (capacity t1) 10) (= (capacity t2) 10)
         (= (spare) 2) (= (total-cost) 0))
  (:goal (= (level t2) 4)))
"""


def test_numeric() -> None:
    sim = simulator(NUMERIC, NUMERIC_PROBLEM)
    state = run(sim, "pour t1 t2")
    # Los efectos se calculan con los valores de antes: (level t1) era 3 al sumarlo.
    assert state.values[("level", "t2")] == 4
    assert state.values[("level", "t1")] == 0
    assert state.values[("total-cost",)] == 2.5
    assert sim.problem.goal is not None and sim.holds(sim.problem.goal, {}, state)
    operator, binding = sim.action("pour", ["t1", "t2"])
    assert not sim.applicable(operator, binding, state)  # (> (level t1) 0)
    state = run(sim, "double t2", "halve t2", state=state)
    assert state.values[("level", "t2")] == 8  # 4 · 2 / 1
    assert state.values[("spare",)] == 1


def test_numeric_errors() -> None:
    sim = simulator(NUMERIC, NUMERIC_PROBLEM.replace("(= (level t2) 1)", ""))
    operator, binding = sim.action("pour", ["t1", "t2"])
    with pytest.raises(SimulationError, match=r"the fluent \(level t2\) has no value"):
        sim.applicable(operator, binding, sim.initial_state())
    sim = simulator(NUMERIC, NUMERIC_PROBLEM.replace("(= (spare) 2)", "(= (spare) 0)"))
    state = sim.initial_state()
    operator, binding = sim.action("halve", ["t1"])
    with pytest.raises(SimulationError, match="scale-down by zero"):
        sim.successor(operator, binding, state)


def test_unsupported() -> None:
    durative = """
    (define (domain d) (:requirements :durative-actions)
      (:predicates (p))
      (:durative-action a :parameters () :duration (= ?duration 1)
        :condition (at start (p)) :effect (at end (not (p)))))
    """
    problem = "(define (problem q) (:domain d) (:init (p)) (:goal (not (p))))"
    with pytest.raises(Unsupported, match="durative-action"):
        simulator(durative, problem)
    til = BLOCKS_PROBLEM.replace("(handempty))", "(handempty) (at 10 (clear a)))")
    with pytest.raises(Unsupported, match="timed initial literals"):
        simulator(BLOCKS, til).initial_state()
