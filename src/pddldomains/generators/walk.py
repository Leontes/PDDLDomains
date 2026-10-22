"""Generador genérico por paseo aleatorio, para cualquier colección clásica.

La explicación está en :class:`RandomWalkGenerator` (es lo que muestra ``--params``). Las
acciones se aplican con :class:`pddldomains.simulator.Simulator`; aquí solo se buscan al azar
argumentos con los que sean aplicables.
"""

import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pddldomains.analysis import Analyzer
from pddldomains.catalog import Catalog, Collection
from pddldomains.generators.base import GeneratedProblem, Generator, GeneratorError, Param
from pddldomains.i18n import _
from pddldomains.pddl import (
    Domain,
    Operator,
    Problem,
    read_domain,
    read_problem,
    read_text,
    typed_list,
)
from pddldomains.sexpr import SExpr, SList, to_text
from pddldomains.simulator import Atom, Binding, SimulationError, Simulator, State

#: Expansiones como mucho al buscar unos argumentos aplicables para un operador.
SEARCH_BUDGET = 20000


class _Walker(Simulator):
    """El simulador, con la búsqueda de acciones aplicables al azar."""

    # --- Búsqueda de argumentos aplicables ----------------------------------------------------

    def find_binding(
        self,
        operator: Operator,
        state: State,
        by_predicate: dict[str, list[Atom]],
        rng: random.Random,
    ) -> Binding | None:
        """Unos argumentos al azar con los que ``operator`` es aplicable, o ``None``."""
        precondition = operator.fields.get(":precondition", SList(0))
        literals = list(_conjuncts(precondition))
        positives = [lit for lit in literals if lit[0] not in ("not", "=")]
        parameters = {p.name: p.type for p in operator.parameters}
        budget = [SEARCH_BUDGET]

        def candidates(variable: str, binding: Binding) -> list[str]:
            # Los valores posibles de la variable según los hechos de los átomos positivos
            # de la precondición que la mencionan (y son compatibles con lo ya ligado).
            allowed: set[str] | None = None
            for atom in positives:
                positions = [i for i, a in enumerate(atom[1:]) if a == variable]
                if not positions or not isinstance(atom[0], str):
                    continue
                values = {
                    fact[1 + positions[0]]
                    for fact in by_predicate.get(atom[0], ())
                    if _matches(atom, fact, binding) and len({fact[1 + i] for i in positions}) == 1
                }
                allowed = values if allowed is None else allowed & values
            typed = self.objects_of(parameters[variable])
            result = [o for o in typed if allowed is None or o in allowed]
            rng.shuffle(result)
            return result

        def consistent(binding: Binding) -> bool:
            for literal in literals:
                variables = _variables_in(literal)
                if variables <= binding.keys() and not self.holds(literal, binding, state):
                    return False
            return True

        def search(binding: Binding) -> Binding | None:
            budget[0] -= 1
            if budget[0] <= 0:
                return None
            unbound = [v for v in parameters if v not in binding]
            if not unbound:
                return binding if self.holds(precondition, binding, state) else None
            options = {v: candidates(v, binding) for v in unbound}
            variable = min(unbound, key=lambda v: len(options[v]))
            for value in options[variable]:
                extended = {**binding, variable: value}
                if consistent(extended):
                    found = search(extended)
                    if found is not None:
                        return found
                if budget[0] <= 0:
                    return None
            return None

        return search({})

    def step(
        self, state: State, visited: set[frozenset[Atom]], rng: random.Random
    ) -> tuple[Operator, Binding, State] | None:
        """Una acción al azar aplicable en ``state`` (mejor si lleva a un estado nuevo).

        Los estados se distinguen por sus átomos: los valores numéricos (el coste) no cuentan.
        """
        by_predicate: dict[str, list[Atom]] = {}
        for atom in state.facts:
            by_predicate.setdefault(atom[0], []).append(atom)
        operators = list(self.operators.values())
        rng.shuffle(operators)
        fallback = None
        for operator in operators:
            binding = self.find_binding(operator, state, by_predicate, rng)
            if binding is None:
                continue
            successor = self.successor(operator, binding, state)
            if successor.atoms not in visited:
                return operator, binding, successor
            fallback = fallback or (operator, binding, successor)
        return fallback


def _matches(atom: SList, fact: Atom, binding: Binding) -> bool:
    """Si un hecho encaja con un átomo de la precondición dados los argumentos ya ligados."""
    if len(fact) != len(atom):
        return False
    for term, value in zip(atom[1:], fact[1:], strict=True):
        if not isinstance(term, str):
            return False
        if term.startswith("?"):
            if term in binding and binding[term] != value:
                return False
        elif term != value:
            return False
    return True


def _conjuncts(node: SExpr) -> Iterator[SList]:
    if isinstance(node, SList) and node:
        if node[0] == "and":
            for child in node[1:]:
                yield from _conjuncts(child)
        else:
            yield node


def _variables_in(node: SExpr) -> set[str]:
    if isinstance(node, str):
        return {node} if node.startswith("?") else set()
    if node and node[0] in ("exists", "forall"):
        bound = (
            {v.name for v in typed_list(list(node[1]), [], 0)}
            if isinstance(node[1], SList)
            else set()
        )
        return _variables_in(node[2]) - bound
    return set().union(*(_variables_in(child) for child in node)) if node else set()


def _walk(
    simulator: _Walker, state: State, steps: int, rng: random.Random
) -> tuple[list[State], list[str]]:
    """Un paseo de hasta ``steps`` acciones: los estados por los que pasa (empezando por
    ``state``) y las acciones. Se para antes si llega a un estado sin acciones aplicables."""
    states = [state]
    visited = {state.atoms}
    plan = []
    for _step in range(steps):
        result = simulator.step(state, visited, rng)
        if result is None:
            break
        operator, binding, state = result
        states.append(state)
        visited.add(state.atoms)
        arguments = " ".join(binding[p.name] for p in operator.parameters)
        plan.append(f"({operator.name}{' ' + arguments if arguments else ''})")
    return states, plan


class RandomWalkGenerator(Generator):
    """Genérico, para cualquier colección clásica sin predicados derivados.

    Parte de un problema de la colección (``base``, por defecto el más pequeño): sus objetos y
    su estado inicial. Aplica ``steps`` acciones al azar, prefiriendo las que llevan a estados
    nuevos, y toma como objetivo ``goals`` hechos del estado final que no estaban al principio,
    primero de los predicados del objetivo del problema base (``on`` en blocks, ``at`` en
    gripper…). El paseo es un plan válido, así que el problema tiene solución; se guarda junto
    al problema y ``generate`` lo valida con VAL si está compilado.

    Con ``mode=both`` cambia también el estado inicial: se da un paseo del doble de largo y el
    estado de la mitad pasa a ser el inicial.

    Admite STRIPS y ADL: tipos, negación, disyunción, cuantificadores, igualdad y efectos
    condicionales; los costes de acción no influyen en el paseo.
    """

    name = "random-walk"
    collection = ""
    description = (
        "genérico para colecciones clásicas: objetivo (y estado inicial) por paseo aleatorio"
    )
    params = (
        Param("collection", str, None, "colección clásica del catálogo (obligatorio)"),
        Param("base", str, "", "problema de partida (por defecto, el más pequeño)"),
        Param("steps", int, "10..40", "acciones del paseo", minimum=1),
        Param("goals", int, "2..6", "átomos del objetivo", minimum=1),
        Param(
            "mode",
            str,
            "goal",
            "goal: nuevo objetivo; both: nuevo estado inicial y objetivo",
            choices=("goal", "both"),
        ),
    )

    def collection_of(self, catalog: Catalog, params: dict[str, Any]) -> Collection:
        if not params.get("collection"):
            raise GeneratorError(_("random-walk necesita -p collection=<colección>"))
        collection = catalog.find(params["collection"])
        analysis = Analyzer(catalog).analyze(collection)
        if "classical" not in analysis.tags or "derived" in analysis.tags:
            raise GeneratorError(
                _(
                    "random-walk solo admite colecciones clásicas sin predicados derivados "
                    "('{collection}' es {tags})",
                    collection=collection.id,
                    tags=" ".join(analysis.tags),
                )
            )
        return collection

    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        if params["base"]:
            base = collection.task(params["base"])
        else:
            base = min(collection.tasks, key=lambda t: t.problem.stat().st_size)
        domain = read_domain(read_text(base.domain))
        problem = read_problem(read_text(base.problem))
        try:
            return self._generate(params, seed, name, base.id, domain, problem, base.domain)
        except SimulationError as error:
            raise GeneratorError(str(error)) from error

    def _generate(
        self,
        params: dict[str, Any],
        seed: int,
        name: str,
        base_id: str,
        domain: Domain,
        problem: Problem,
        domain_path: Path,
    ) -> GeneratedProblem:
        simulator = _Walker(domain, problem)
        initial = simulator.initial_state()
        if "total-cost" in simulator.functions and ("total-cost",) not in initial.values:
            # Un problema que no inicializa el coste: para el paseo, empieza en 0.
            initial = simulator.make_state(initial.atoms, {**initial.values, ("total-cost",): 0})
        goal_predicates = {atom[0] for atom in _goal_atoms(problem.goal)}
        rng = random.Random(seed)
        for _attempt in range(20):  # si el paseo no cambia nada, otro intento
            if params["mode"] == "both":
                # Un solo paseo del doble de largo, partido por la mitad: el estado del medio
                # es el inicial y la segunda mitad, el plan. (Dos paseos seguidos fallan en
                # dominios con callejones sin salida, como slitherlink.)
                states, plan = _walk(simulator, initial, 2 * params["steps"], rng)
                middle = len(plan) // 2
                start, plan = states[middle], plan[middle:]
            else:
                states, plan = _walk(simulator, initial, params["steps"], rng)
                start = initial
            final = states[-1]
            changed = sorted(
                a for a in final.atoms - start.atoms if a[0] in simulator.fluent_predicates
            )
            if changed:
                break
        else:
            raise GeneratorError(
                _(
                    "los paseos desde {base} no cambian nada (¿no hay acciones aplicables?)",
                    base=base_id,
                )
            )
        # Primero los predicados del objetivo del problema base; si no llegan, los demás.
        preferred = [a for a in changed if a[0] in goal_predicates]
        others = [a for a in changed if a[0] not in goal_predicates]
        goals = rng.sample(preferred, min(params["goals"], len(preferred)))
        goals += rng.sample(others, min(params["goals"] - len(goals), len(others)))
        text = _write(
            name, domain, problem, start.atoms if params["mode"] == "both" else None, sorted(goals)
        )
        notes = {"base": base_id, "plan-length": len(plan)}
        comment = _("{count} acciones (paseo aleatorio)", count=len(plan))
        plan_text = "\n".join(plan) + f"\n; {comment}\n"
        return GeneratedProblem(text, plan_text, notes, domain=domain_path)


def _goal_atoms(node: SExpr | None) -> Iterator[Atom]:
    if isinstance(node, SList) and node:
        if node[0] in ("and", "or", "not", "imply"):
            for child in node[1:]:
                yield from _goal_atoms(child)
        elif node[0] in ("exists", "forall") and len(node) == 3:
            yield from _goal_atoms(node[2])
        elif isinstance(node[0], str):
            yield (node[0],)


def _write(
    name: str,
    domain: Domain,
    problem: Problem,
    new_init: frozenset[Atom] | None,
    goals: list[Atom],
) -> str:
    lines = [
        "; " + _("Generado por paseo aleatorio desde el problema '{name}'", name=problem.name),
        f"(define (problem {name})",
    ]
    lines.append(f"  (:domain {domain.name})")
    if problem.objects:
        lines.append("  (:objects")
        groups: dict[str, list[str]] = {}
        for typed in problem.objects:
            type_ = (
                typed.type
                if isinstance(typed.type, str)
                else "(either " + " ".join(typed.type) + ")"
            )
            groups.setdefault(type_ if typed.explicit else "", []).append(typed.name)
        for type_, names in groups.items():
            lines.append(f"    {' '.join(names)}" + (f" - {type_}" if type_ else ""))
        lines.append("  )")
    lines.append("  (:init")
    if new_init is None:
        lines.extend(f"    {to_text(fact, 0)}" for fact in problem.init or ())
    else:
        lines.extend(f"    ({' '.join(atom)})" for atom in sorted(new_init))
        numeric = [f for f in problem.init or () if isinstance(f, SList) and f and f[0] == "="]
        lines.extend(f"    {to_text(fact, 0)}" for fact in numeric)
    lines.append("  )")
    lines.append("  (:goal (and")
    lines.extend(f"    ({' '.join(atom)})" for atom in goals)
    lines.append("  ))")
    if problem.metric is not None:
        lines.append(f"  (:metric {problem.metric[0]} {to_text(problem.metric[1], 0)})")
    lines.append(")")
    return "\n".join(lines) + "\n"
