"""Revisión: cada errata encontrada al reunir el catálogo, reproducida en pequeño.

Cada caso es la versión mínima de una errata real (ver las fichas de ``dominios/``). Si el
revisor deja de encontrarla, el test lo dice.
"""

from pathlib import Path

import pytest
from conftest import Writer

from pddldomains.catalog import Catalog
from pddldomains.lint import Finding, lint_domain, lint_problem

DOMAIN = """(define (domain d)
  (:requirements :strips :typing)
  (:types item place)
  (:predicates (at ?i - item ?p - place) (free ?p - place))
  (:action move :parameters (?i - item ?a ?b - place)
    :precondition (and (at ?i ?a) (free ?b))
    :effect (and (not (at ?i ?a)) (at ?i ?b) (free ?a) (not (free ?b)))))"""

PROBLEM = """(define (problem p1) (:domain d)
  (:objects i1 - item a b - place)
  (:init (at i1 a) (free b))
  (:goal (at i1 b)))"""


def codes(findings: list[Finding], level: str | None = None) -> set[str]:
    return {f.code for f in findings if level is None or f.level == level}


def check(write: Writer, domain: str, problem: str | None = None) -> set[str]:
    domain_path = write("domain.pddl", domain)
    parsed, findings = lint_domain(domain_path)
    if problem is not None:
        assert parsed is not None
        findings += lint_problem(write("p01.pddl", problem), parsed)
    return codes(findings)


def test_clean_domain_and_problem(write: Writer) -> None:
    assert check(write, DOMAIN, PROBLEM) == set()


@pytest.mark.parametrize(
    ("before", "after", "code"),
    [
        # (*) floor-tile: total-cost sin :action-costs
        (
            "(free ?a) (not (free ?b))",
            "(free ?a) (not (free ?b)) (increase (total-cost) 1)",
            "undeclared-requirement",
        ),
        # (*) tidybot / pathways: not en la precondición sin :negative-preconditions
        (
            "(and (at ?i ?a) (free ?b))",
            "(and (at ?i ?a) (not (at ?i ?b)))",
            "undeclared-requirement",
        ),
        # (‡) tpp y generator: guion pegado al tipo
        ("?b - place)", "?b -place)", "glued-dash"),
        # (‡) generator-toricelli: espacio tras la interrogación
        ("(free ?b))", "(free ? b))", "malformed-variable"),
        # (‡) storage: tipo declarado dos veces
        ("(:types item place)", "(:types item place place)", "repeated-declaration"),
        # (‡) satellite: el dominio se llama como un tipo
        ("(domain d)", "(domain place)", "shared-name"),
        # (‡) floor-tile: una acción se llama como un predicado
        ("(:action move", "(:action free", "shared-name"),
        # Nombres sin declarar
        ("(free ?b))", "(fre ?b))", "undeclared-predicate"),
        ("(at ?i ?b)", "(at ?i ?c)", "unbound-variable"),
        ("(at ?i ?b)", "(at ?i ?b ?a)", "arity"),
        ("?b - place)", "?b - plac)", "undeclared-type"),
    ],
)
def test_domain_errata(write: Writer, before: str, after: str, code: str) -> None:
    assert before in DOMAIN
    assert code in check(write, DOMAIN.replace(before, after, 1))


@pytest.mark.parametrize(
    ("before", "after", "code"),
    [
        # (‡) woodworking p10: una línea '- board' sin objetos
        ("a b - place)", "a b - place - item)", "type-without-names"),
        # (‡) parking: el problema se llama como el dominio
        ("(problem p1)", "(problem d)", "shared-name"),
        # (‡) tidybot: un objeto se llama como su tipo
        ("i1 - item", "item - item", "shared-name"),
        # (‡) generator-nonlinear: el problema es de otro dominio
        ("(:domain d)", "(:domain d2)", "domain-mismatch"),
        ("(at i1 b)", "(at i2 b)", "undeclared-object"),
        ("(:goal (at i1 b))", "", "missing-goal"),
        # VAL falla sin :init
        ("(:init (at i1 a) (free b))", "", "val-missing-init"),
        ("(at i1 a) (free b)", "(at i1 a) (free b) (free b)", "repeated-fact"),
        ("(at i1 a) (free b)", "(at a i1) (free b)", "incompatible-type"),
    ],
)
def test_problem_errata(write: Writer, before: str, after: str, code: str) -> None:
    assert before in PROBLEM
    assert code in check(write, DOMAIN, PROBLEM.replace(before, after, 1))


NUMERIC = """(define (domain n)
  (:requirements :typing :numeric-fluents)
  (:types tank)
  (:functions (level ?t - tank) (rate ?t - tank) (d))
  (:action fill :parameters (?t - tank) :precondition (< (level ?t) 10)
    :effect (and (increase (level ?t) (rate ?t)) (increase (d) 1))))"""


def numeric_problem(init: str) -> str:
    return f"(define (problem q) (:domain n) (:objects t1 - tank) (:init {init}) (:goal (> (d) 1)))"


def test_numeric_errata(write: Writer) -> None:
    ok = "(= (level t1) 0) (= (rate t1) 1) (= (d) 0)"
    assert check(write, NUMERIC, numeric_problem(ok)) == set()
    # (‡) car: función sin argumentos sin paréntesis
    assert "function-without-parentheses" in check(
        write, NUMERIC, numeric_problem(ok.replace("(d)", "d"))
    )
    # (‡) pathways: dos valores iniciales para la misma función
    assert "repeated-value" in check(write, NUMERIC, numeric_problem(ok + " (= (d) 3)"))
    # (‡) generator-events: una función que el dominio lee y el problema no inicializa
    without_rate = "(= (level t1) 0) (= (d) 0)"
    assert "uninitialized-function" in check(write, NUMERIC, numeric_problem(without_rate))
    # (*) counters/zenotravel: la línea :requirements comentada
    commented = NUMERIC.replace("(:requirements", ";(:requirements")
    assert "undeclared-requirement" in check(write, commented)


def test_val_warnings(write: Writer) -> None:
    domain = DOMAIN.replace(
        "(:requirements :strips :typing)", "(:requirements :strips :typing :constraints)"
    )
    empty = PROBLEM.replace("(:goal (at i1 b))", "(:goal (at i1 b)) (:constraints (and))")
    assert "val-empty-constraints" in check(write, domain, empty)
    hold_after = PROBLEM.replace(
        "(:goal (at i1 b))", "(:goal (at i1 b)) (:constraints (hold-after 2 (free a)))"
    )
    assert "val-hold-after" in check(write, domain, hold_after)
    function_like_domain = NUMERIC.replace("(d))", "(d) (n))")
    assert "val-function-named-like-domain" in check(write, function_like_domain)


def test_line_numbers(write: Writer) -> None:
    path = write("domain.pddl", DOMAIN.replace("(free ?b))", "(fre ?b))", 1))
    _, findings = lint_domain(path)
    (finding,) = [f for f in findings if f.code == "undeclared-predicate"]
    assert finding.line == 6
    assert finding.format(path.parent).startswith("domain.pddl:6: error [undeclared-predicate]")


def test_syntax_error(write: Writer) -> None:
    parsed, findings = lint_domain(write("domain.pddl", DOMAIN + ")"))
    assert parsed is None
    assert codes(findings) == {"syntax"}


def test_catalog_has_no_errors(catalog: Catalog) -> None:
    """Todas las erratas del catálogo están corregidas: la revisión no da ningún error."""
    errors = []
    for collection in catalog:
        domains = {}
        for path in collection.domain_files():
            domains[path], findings = lint_domain(path)
            errors += [f for f in findings if f.level == "error"]
        for task in collection.tasks:
            domain = domains[task.domain]
            assert domain is not None
            errors += [f for f in lint_problem(task.problem, domain) if f.level == "error"]
    assert errors == [], "\n".join(f.format(Path.cwd()) for f in errors[:20])
