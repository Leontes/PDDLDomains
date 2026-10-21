"""Detección de los requisitos usados y clasificación por tipos."""

import pytest

from pddldomains.features import (
    classify,
    domain_uses,
    expand_requirements,
    level_of,
    parse_level,
    problem_uses,
    undeclared,
    used_requirements,
)
from pddldomains.pddl import read_domain, read_problem


def used_by(domain_text: str, problem_text: str | None = None) -> frozenset[str]:
    domain = read_domain(domain_text)
    uses = domain_uses(domain)
    if problem_text is not None:
        uses += problem_uses(read_problem(problem_text), domain)
    return used_requirements(uses)


def action(precondition: str = "(and)", effect: str = "(and)") -> str:
    """Un dominio con una acción (sin :functions, para que solo cuente lo que usa la acción)."""
    return (
        "(define (domain d) (:predicates (p ?x) (q ?x))"
        f" (:action a :parameters (?x) :precondition {precondition} :effect {effect}))"
    )


@pytest.mark.parametrize(
    ("precondition", "effect", "expected"),
    [
        ("(p ?x)", "(q ?x)", set()),
        ("(not (p ?x))", "(q ?x)", {":negative-preconditions"}),
        ("(or (p ?x) (q ?x))", "(q ?x)", {":disjunctive-preconditions"}),
        ("(not (and (p ?x) (q ?x)))", "(q ?x)", {":disjunctive-preconditions"}),
        ("(exists (?y) (p ?y))", "(q ?x)", {":existential-preconditions"}),
        ("(forall (?y) (p ?y))", "(q ?x)", {":universal-preconditions"}),
        ("(= ?x ?x)", "(q ?x)", {":equality"}),
        ("(p ?x)", "(when (p ?x) (q ?x))", {":conditional-effects"}),
        ("(p ?x)", "(forall (?y) (q ?y))", {":conditional-effects"}),
        ("(p ?x)", "(increase (total-cost) 1)", {":action-costs"}),
        ("(> (f) 0)", "(q ?x)", {":numeric-fluents"}),
        ("(p ?x)", "(increase (f) 1)", {":numeric-fluents"}),
    ],
)
def test_formula_and_effect_rules(precondition: str, effect: str, expected: set[str]) -> None:
    assert used_by(action(precondition, effect)) == expected


def test_temporal_rules() -> None:
    domain = """(define (domain d) (:requirements :durative-actions) (:predicates (p))
      (:functions (f))
      (:durative-action a :parameters () :duration (and (>= ?duration 1) (<= ?duration 5))
       :condition (at start (p)) :effect (and (at end (not (p))) (increase (f) (* #t 1)))))"""
    used = used_by(domain)
    assert {":durative-actions", ":duration-inequalities", ":continuous-effects"} <= used
    assert ":numeric-fluents" in used


def test_pddlplus_process_does_not_need_continuous_effects() -> None:
    domain = """(define (domain d) (:predicates (on)) (:functions (x))
      (:process p :parameters () :precondition (on) :effect (increase (x) (* #t 1))))"""
    used = used_by(domain)
    assert ":time" in used and ":numeric-fluents" in used
    assert ":continuous-effects" not in used


def test_problem_rules() -> None:
    domain = "(define (domain d) (:predicates (p)) (:functions (total-cost)))"
    problem = """(define (problem x) (:domain d) (:init (at 10 (p)) (= (total-cost) 0))
      (:goal (preference g (p))) (:constraints (sometime (p)))
      (:metric minimize (is-violated g)))"""
    used = used_by(domain, problem)
    assert {":timed-initial-literals", ":preferences", ":constraints"} <= used
    assert ":numeric-fluents" not in used  # una métrica solo con is-violated no la necesita


def test_total_time_metric_needs_numeric_fluents() -> None:
    domain = "(define (domain d) (:predicates (p)))"
    problem = "(define (problem x) (:domain d) (:init) (:goal (p)) (:metric minimize (total-time)))"
    assert ":numeric-fluents" in used_by(domain, problem)


def test_undeclared_and_expansions() -> None:
    domain = read_domain(action("(not (p ?x))", "(increase (total-cost) 1)"))
    assert [u.requirement for u in undeclared(domain_uses(domain), [":strips"])] == [
        ":negative-preconditions",
        ":action-costs",
    ]
    assert undeclared(domain_uses(domain), [":adl", ":numeric-fluents"]) == []
    assert ":negative-preconditions" in expand_requirements([":adl"])
    assert expand_requirements([]) == {":strips"}


def test_classification() -> None:
    assert classify(frozenset({":typing"})) == ["classical", "strips"]
    assert classify(frozenset({":conditional-effects", ":action-costs"})) == [
        "classical",
        "adl",
        "costs",
    ]
    assert classify(frozenset({":durative-actions", ":numeric-fluents"})) == ["numeric", "temporal"]


@pytest.mark.parametrize(
    ("used", "level"),
    [
        (set(), 1),
        ({":typing"}, 2),  # los tipos van con ADL: el nivel 1 es STRIPS puro
        ({":negative-preconditions"}, 2),
        ({":typing", ":action-costs"}, 3),  # costes de acción: con los fluentes numéricos
        ({":durative-actions"}, 3),
        ({":derived-predicates", ":typing"}, 4),
        ({":timed-initial-literals", ":durative-actions"}, 4),
        ({":object-fluents"}, 5),
        ({":preferences", ":durative-actions"}, 5),
        ({":time", ":preferences"}, 6),
    ],
)
def test_levels(used: set[str], level: int) -> None:
    assert level_of(frozenset(used)).number == level


def test_parse_level() -> None:
    assert parse_level(3).name == "PDDL 2.1"
    assert parse_level("PDDL 2.2").number == parse_level("2.2").number == 4
    assert parse_level("strips").number == 1
    assert parse_level("adl").number == 2
    assert parse_level("pddl+").number == parse_level("PDDLPLUS").number == 6
    with pytest.raises(ValueError, match="unknown level"):
        parse_level("7")
