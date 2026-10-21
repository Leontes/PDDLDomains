"""Lectura de S-expresiones y estructura de dominios y problemas."""

import pytest

from pddldomains.pddl import Issue, PDDLStructureError, read_domain, read_problem, typed_list
from pddldomains.sexpr import LineIndex, PDDLSyntaxError, SList, is_number, parse, to_text


def test_parse_lowercases_and_skips_comments() -> None:
    (expression,) = parse("(Define ; comentario\n  (Domain X))")
    assert isinstance(expression, SList)
    assert expression == ["define", ["domain", "x"]]
    assert to_text(expression) == "(define (domain x))"


def test_unbalanced_parentheses_report_position() -> None:
    with pytest.raises(PDDLSyntaxError) as error:
        parse("(a (b)")
    assert error.value.offset == 0
    with pytest.raises(PDDLSyntaxError):
        parse("(a))")


def test_line_index() -> None:
    lines = LineIndex("a\nb\nc")
    assert [lines.line(i) for i in (0, 2, 4)] == [1, 2, 3]


@pytest.mark.parametrize("token", ["0", "-1", "2.5", ".5", "1e3"])
def test_numbers(token: str) -> None:
    assert is_number(token)


def test_typed_list_with_glued_dash_and_missing_names() -> None:
    issues: list[Issue] = []
    names = typed_list(["a", "b", "-", "t", "c", "-tank", "-", "u"], issues, 0)
    assert [(n.name, n.type) for n in names] == [("a", "t"), ("b", "t"), ("c", "tank")]
    assert [i.code for i in issues] == ["glued-dash", "type-without-names"]


def test_read_domain_sections() -> None:
    domain = read_domain(
        """(define (domain d) (:requirements :typing) (:types a b - object)
        (:predicates (p ?x - a)) (:functions (f) - number (g ?x - a) - b)
        (:action act :parameters (?x - a) :precondition (p ?x) :effect (not (p ?x))))"""
    )
    assert domain.name == "d"
    assert [p.name for p in domain.predicates] == ["p"]
    assert [(f.name, f.type) for f in domain.functions] == [("f", "number"), ("g", "b")]
    assert domain.operators[0].name == "act"
    assert set(domain.operators[0].fields) == {":precondition", ":effect"}


def test_read_problem_sections() -> None:
    problem = read_problem(
        "(define (problem p) (:domain d) (:objects x - a) (:init (p x)) (:goal (p x))"
        " (:metric minimize (total-time)))"
    )
    assert problem.domain_name == "d"
    assert problem.init == [["p", "x"]]
    assert problem.metric is not None and problem.metric[0] == "minimize"


def test_not_a_define() -> None:
    with pytest.raises(PDDLStructureError):
        read_domain("(foo)")
