"""Trazas de plan: los estados por los que pasa un plan, con degradación reproducible.

Se ejecuta el plan sobre el problema (con :mod:`pddldomains.simulator`, comprobando la
precondición de cada acción) y se escribe una traza en JSON: el estado inicial, cada acción
con sus argumentos y el estado que deja, con el paso y el instante de cada uno.

Cada estado da el valor de los átomos del universo (cierto, falso o desconocido) y de los
fluentes numéricos, incluidos los constantes. El universo (:func:`atom_universe`) son, por
defecto, todas las instancias de los predicados que cambian las acciones y los átomos
estáticos ciertos al principio; un átomo de fuera del universo es falso en todos los estados.
Con ``world = "closed"`` no se listan los falsos: un átomo que no está entre los ciertos ni
entre los desconocidos es falso. Con ``"open"`` se listan los tres.

Degradación (:class:`Degradation`), aplicada a las observaciones y anotada en la traza:

* ``missing``: porcentaje de átomos y de valores numéricos de cada estado que pasan a ser
  desconocidos;
* ``missing_states``: porcentaje de estados que faltan enteros;
* ``noise``: porcentaje de los átomos observados de cada estado cuyo valor se invierte, y de
  los valores numéricos observados que se alteran (hasta ``numeric_noise`` por ciento, al
  alza o a la baja).

Los porcentajes se aplican exactamente en cada estado (redondeando) y son reproducibles: cada
elección usa su propia semilla, derivada de ``seed``, del tipo de degradación y del estado.
Por eso las degradaciones están anidadas: con la misma semilla, los huecos de un 30 %
incluyen los de un 20 %, y lo mismo con el ruido y los estados que faltan.

Las acciones no se degradan.
"""

import hashlib
import json
import math
import random
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any, TextIO

from pddldomains import __version__
from pddldomains.catalog import Catalog, CatalogError, is_domain_file
from pddldomains.i18n import _
from pddldomains.pddl import (
    Domain,
    PDDLStructureError,
    Problem,
    read_domain,
    read_problem,
    read_text,
    typed_list,
)
from pddldomains.sexpr import PDDLSyntaxError, to_text
from pddldomains.simulator import Atom, SimulationError, Simulator, State, Term, atom_text

#: Nombre y versión del formato de las trazas.
FORMAT = "pddldomains-trace"
FORMAT_VERSION = 1
#: Átomos como mucho en el universo de una traza (por defecto).
MAX_ATOMS = 250_000
#: Los universos de átomos posibles (ver :func:`atom_universe`).
UNIVERSES = ("dynamic", "typed")

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_PLAN_LINE = re.compile(
    rf"^(?:(?P<time>{_NUMBER})\s*:\s*)?\((?P<action>[^()]*)\)\s*(?:\[(?P<duration>{_NUMBER})\])?$"
)


class TraceError(Exception):
    """Un plan ilegible o que no se puede ejecutar, o parámetros no válidos."""


@dataclass(frozen=True)
class PlanStep:
    """Una acción del plan.

    Attributes:
        name: nombre de la acción.
        arguments: sus argumentos.
        time: instante, si el plan lo da (``0.000: (acción ...)``).
        duration: duración, si el plan la da (``[1.000]``).
    """

    name: str
    arguments: tuple[str, ...]
    time: float | None = None
    duration: float | None = None

    @property
    def text(self) -> str:
        """La acción en PDDL: ``(unstack a b)``."""
        return atom_text((self.name, *self.arguments))


def parse_plan(text: str) -> list[PlanStep]:
    """Lee un plan: una acción por línea, ``(acción args)`` o ``t: (acción args) [d]``.

    Los comentarios (``;``) y las líneas vacías se ignoran.
    """
    steps = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        match = _PLAN_LINE.match(line)
        if match is None:
            raise TraceError(
                _("línea {line} del plan no válida: '{content}'", line=number, content=raw.strip())
            )
        words = match["action"].lower().split()
        if not words:
            raise TraceError(_("línea {line} del plan sin acción", line=number))
        steps.append(
            PlanStep(
                words[0],
                tuple(words[1:]),
                float(match["time"]) if match["time"] else None,
                float(match["duration"]) if match["duration"] else None,
            )
        )
    return steps


@dataclass
class Execution:
    """La ejecución de un plan: los estados (el inicial y uno por acción) y las acciones."""

    simulator: Simulator
    domain: Domain
    problem: Problem
    steps: list[PlanStep]
    states: list[State]
    goal_reached: bool


def execute(domain: Domain, problem: Problem, steps: Sequence[PlanStep]) -> Execution:
    """Ejecuta el plan desde el estado inicial, comprobando la precondición de cada acción.

    Si el plan da instantes, las acciones se ordenan por instante (es un plan secuencial).
    """
    timed = [step.time for step in steps if step.time is not None]
    if timed and len(timed) != len(steps):
        raise TraceError(_("el plan mezcla acciones con instante y sin él"))
    if timed:
        steps = sorted(steps, key=lambda step: step.time or 0.0)
    try:
        simulator = Simulator(domain, problem)
        state = simulator.initial_state()
        states = [state]
        for index, step in enumerate(steps, 1):
            operator, binding = simulator.action(step.name, list(step.arguments))
            if not simulator.applicable(operator, binding, state):
                failing = simulator.unsatisfied(operator, binding, state)
                raise TraceError(
                    _(
                        "la acción {index} del plan, {action}, no es aplicable: "
                        "no se cumple {condition}",
                        index=index,
                        action=step.text,
                        condition=to_text(failing) if failing is not None else "?",
                    )
                )
            state = simulator.successor(operator, binding, state)
            states.append(state)
        goal_reached = problem.goal is None or simulator.holds(problem.goal, {}, state)
    except SimulationError as error:
        raise TraceError(str(error)) from error
    return Execution(simulator, domain, problem, list(steps), states, goal_reached)


@dataclass(frozen=True)
class Degradation:
    """Cómo se degradan las observaciones (porcentajes de 0 a 100).

    Attributes:
        missing: átomos y valores numéricos de cada estado que pasan a ser desconocidos.
        missing_states: estados que faltan enteros.
        noise: átomos observados que se invierten y valores numéricos observados que se
            alteran.
        numeric_noise: cuánto se altera como mucho un valor numérico, en porcentaje de su
            valor.
        seed: semilla.
    """

    missing: float = 0.0
    missing_states: float = 0.0
    noise: float = 0.0
    numeric_noise: float = 10.0
    seed: int = 0

    def check(self) -> None:
        """Comprueba que los porcentajes están entre 0 y 100."""
        for name in ("missing", "missing_states", "noise"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise TraceError(
                    _("{name} tiene que estar entre 0 y 100 (es {value})", name=name, value=value)
                )
        if self.numeric_noise < 0:
            raise TraceError(_("numeric_noise no puede ser negativo"))


@dataclass
class Provenance:
    """De dónde sale una traza: el planificador que dio el plan (lo que se sepa)."""

    planner: str | None = None
    config: str | None = None
    seed: int | None = None


@dataclass
class _Counters:
    hidden_atoms: int = 0
    hidden_values: int = 0
    flipped_atoms: int = 0
    perturbed_values: int = 0
    missing_states: list[int] = field(default_factory=list)


def atom_universe(
    simulator: Simulator,
    states: Iterable[State] = (),
    kind: str = "dynamic",
    max_atoms: int = MAX_ATOMS,
) -> list[Atom]:
    """Los átomos de los que la traza da el valor en cada estado, ordenados.

    Con ``kind="typed"``, todos los que encajan con los tipos de los predicados. Con
    ``"dynamic"``, los de los predicados que cambian las acciones (y los derivados) y, de
    los estáticos, solo los ciertos en el estado inicial: los demás son falsos en todos los
    estados. Se añaden siempre los ciertos en ``states`` (un estado inicial que no respeta
    los tipos, por ejemplo), para no perderlos.
    """
    if kind not in UNIVERSES:
        raise TraceError(
            _(
                "universo desconocido '{kind}' (se esperaba {expected})",
                kind=kind,
                expected=", ".join(UNIVERSES),
            )
        )
    signatures = {p.name: [t.type for t in p.parameters] for p in simulator.domain.predicates}
    for head, _body in simulator.domain.derived:  # derivados que no se declaran en :predicates
        if head and isinstance(head[0], str) and head[0] not in signatures:
            signatures[head[0]] = [t.type for t in typed_list(list(head[1:]), [], 0)]
    if kind == "dynamic":
        changing = simulator.fluent_predicates | simulator.derived_predicates
        signatures = {name: types for name, types in signatures.items() if name in changing}
    size = sum(
        math.prod(len(simulator.objects_of(type_)) for type_ in types)
        for types in signatures.values()
    )
    if size > max_atoms:
        raise TraceError(
            _(
                "el problema tiene {size} átomos posibles, más que el máximo ({maximum})",
                size=size,
                maximum=max_atoms,
            )
        )
    atoms: set[Atom] = set()
    for name, types in signatures.items():
        for arguments in product(*(simulator.objects_of(type_) for type_ in types)):
            atoms.add((name, *arguments))
    for state in states:
        atoms |= state.facts
    return sorted(atoms)


def _rng(seed: int, purpose: str, state: int) -> random.Random:
    # Una semilla de texto se convierte en entero con SHA-512: la misma en cualquier ejecución.
    return random.Random(f"{seed}:{purpose}:{state}")


def _keys(count: int, seed: int, purpose: str, state: int) -> list[float]:
    """Una clave aleatoria por elemento; los de clave más baja son los elegidos.

    Se usa ``random()``, cuya secuencia Python garantiza entre versiones (``randbytes`` y
    ``getrandbits``, más rápidos, no).
    """
    uniform = _rng(seed, purpose, state).random
    return [uniform() for _index in range(count)]


def _choose(
    pool: Sequence[int], size: int, percent: float, seed: int, purpose: str, state: int
) -> set[int]:
    """Los ``percent`` por ciento de ``pool`` (redondeando) de clave más baja.

    ``pool`` son índices de 0 a ``size``. Las claves dependen solo de la semilla, de
    ``purpose`` y del estado, no de ``pool`` ni de ``percent``: por eso las elecciones con
    más porcentaje incluyen las de menos.
    """
    count = math.floor(len(pool) * percent / 100 + 0.5)
    if count == 0:
        return set()
    keys = _keys(size, seed, purpose, state)
    return set(sorted(pool, key=keys.__getitem__)[:count])


def _number(value: float) -> int | float:
    """Un valor para el JSON: entero si lo es y sin restos de coma flotante."""
    value = round(value, 10)
    return int(value) if value.is_integer() else value


def build_trace(
    execution: Execution,
    degradation: Degradation,
    *,
    world: str = "closed",
    universe: str = "dynamic",
    provenance: Provenance | None = None,
    files: Mapping[str, Path] | None = None,
    max_atoms: int = MAX_ATOMS,
    val: str | None = None,
    catalog: Catalog | None = None,
) -> dict[str, Any]:
    """La traza de una ejecución, degradada, como diccionario listo para JSON.

    Args:
        execution: la ejecución del plan.
        degradation: cómo se degradan las observaciones.
        world: ``"closed"`` (no se listan los átomos falsos) u ``"open"``.
        universe: los átomos de los que se da el valor (ver :func:`atom_universe`).
        provenance: el planificador que dio el plan.
        files: los ficheros ``"domain"``, ``"problem"`` y ``"plan"``, para la procedencia.
        max_atoms: átomos como mucho en el universo.
        val: el veredicto de VAL sobre el plan, si se ha validado.
        catalog: el catálogo en el que buscar la colección (por defecto, el de siempre).
    """
    degradation.check()
    if world not in ("closed", "open"):
        raise TraceError(_("world tiene que ser 'closed' u 'open' (es '{world}')", world=world))
    simulator = execution.simulator
    observer = _Observer(
        atom_universe(simulator, execution.states, universe, max_atoms),
        sorted({term for state in execution.states for term in state.values}),
        degradation,
        world,
    )
    seed = degradation.seed
    count = len(execution.states)
    missing_states = _choose(
        range(count), count, degradation.missing_states, seed, "missing-states", 0
    )
    counters = observer.counters
    counters.missing_states = sorted(missing_states)
    times = _times(execution.steps)
    states = []
    for index, state in enumerate(execution.states):
        entry: dict[str, Any] = {"step": index, "time": _number(times[index])}
        if index in missing_states:
            entry["missing"] = True
        else:
            entry.update(observer.observe(state, index))
        states.append(entry)
    actions = [
        {
            "step": index,
            "time": _number(step.time if step.time is not None else float(index)),
            "name": step.name,
            "arguments": list(step.arguments),
        }
        for index, step in enumerate(execution.steps, 1)
    ]
    provenance = provenance or Provenance()
    collection, info = _file_info(files or {}, catalog)
    return {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "generator": f"pddldomains {__version__}",
        "collection": collection,
        "domain": {"name": execution.domain.name, **info["domain"]},
        "problem": {"name": execution.problem.name, **info["problem"]},
        "plan": {
            **info["plan"],
            "length": len(execution.steps),
            "planner": provenance.planner,
            "config": provenance.config,
            "seed": provenance.seed,
        },
        "execution": {"goal_reached": execution.goal_reached, "val": val},
        "degradation": {
            "seed": seed,
            "missing_percent": degradation.missing,
            "missing_states_percent": degradation.missing_states,
            "noise_percent": degradation.noise,
            "numeric_noise_percent": degradation.numeric_noise,
            "hidden_atoms": counters.hidden_atoms,
            "hidden_values": counters.hidden_values,
            "flipped_atoms": counters.flipped_atoms,
            "perturbed_values": counters.perturbed_values,
            "missing_states": counters.missing_states,
        },
        "world": world,
        "universe": {"kind": universe, "size": len(observer.atoms)},
        "objects": {
            name: (type_ if isinstance(type_, str) else ["either", *type_])
            for name, type_ in sorted(simulator.object_types.items())
        },
        "states": states,
        "actions": actions,
    }


def _times(steps: Sequence[PlanStep]) -> list[float]:
    """El instante de cada estado: 0 el inicial; el de su acción (más la duración) los demás."""
    times = [0.0]
    for index, step in enumerate(steps, 1):
        if step.time is None:
            times.append(float(index))
        else:
            times.append(step.time + (step.duration or 0.0))
    return times


class _Observer:
    """Lo que se observa de cada estado, con sus huecos y su ruido.

    Las elecciones se hacen sobre posiciones fijas del universo de átomos y de la lista de
    fluentes numéricos de toda la traza, para que estén anidadas (ver :func:`_choose`).
    """

    def __init__(
        self, atoms: list[Atom], terms: list[Term], degradation: Degradation, world: str
    ) -> None:
        self.atoms = atoms
        self.texts = [atom_text(atom) for atom in atoms]  # compartidos por todos los estados
        self.terms = terms
        self.term_texts = [atom_text(term) for term in terms]
        self.degradation = degradation
        self.world = world
        self.counters = _Counters()

    def observe(self, state: State, index: int) -> dict[str, Any]:
        """La observación del estado ``index``."""
        degradation, seed = self.degradation, self.degradation.seed
        size = len(self.atoms)
        hidden = _choose(range(size), size, degradation.missing, seed, "missing", index)
        observed = [i for i in range(size) if i not in hidden] if hidden else range(size)
        flipped = _choose(observed, size, degradation.noise, seed, "noise", index)
        self.counters.hidden_atoms += len(hidden)
        self.counters.flipped_atoms += len(flipped)
        facts = state.facts
        true, false, unknown = [], [], []
        for i, atom in enumerate(self.atoms):
            if i in hidden:
                unknown.append(self.texts[i])
            elif (atom in facts) != (i in flipped):
                true.append(self.texts[i])
            else:
                false.append(self.texts[i])
        size = len(self.terms)
        defined = [i for i, term in enumerate(self.terms) if term in state.values]
        hidden = _choose(defined, size, degradation.missing, seed, "missing-values", index)
        observed = [i for i in defined if i not in hidden]
        perturbed = _choose(observed, size, degradation.noise, seed, "noise-values", index)
        factors = _keys(size, seed, "noise-factors", index) if perturbed else []
        self.counters.hidden_values += len(hidden)
        self.counters.perturbed_values += len(perturbed)
        values: dict[str, int | float] = {}
        for i in observed:
            value = state.values[self.terms[i]]
            if i in perturbed:  # hasta numeric_noise % de su valor (de 1 si es 0), arriba o abajo
                scale = abs(value) or 1.0
                value += (2 * factors[i] - 1) * degradation.numeric_noise / 100 * scale
            values[self.term_texts[i]] = _number(value)
        observation: dict[str, Any] = {"true": true}
        if self.world == "open":
            observation["false"] = false
        observation["unknown"] = unknown
        observation["values"] = values
        observation["unknown_values"] = [self.term_texts[i] for i in sorted(hidden)]
        return observation


def write_trace(trace: Mapping[str, Any], stream: TextIO, *, compact: bool = False) -> None:
    """Escribe la traza en JSON: cada estado y cada acción en una línea, o todo en una con
    ``compact``.

    Se escribe por partes, sin construir el texto entero (una traza grande ocupa cientos de
    MB).
    """
    newline, pad = ("", "") if compact else ("\n", "  ")
    stream.write("{" + newline)
    for position, (key, value) in enumerate(trace.items()):
        if position:
            stream.write("," + newline)
        stream.write(f"{pad}{_dumps(key)}: ")
        if key in ("states", "actions") and value:
            stream.write("[" + newline)
            for index, element in enumerate(value):
                comma = "," if index < len(value) - 1 else ""
                stream.write(f"{pad}{pad}{_dumps(element)}{comma}{newline}")
            stream.write(pad + "]")
        else:
            text = _dumps(value, indent=None if compact else 2)
            stream.write(text.replace("\n", "\n" + pad))
    stream.write(newline + "}\n")


def _dumps(value: Any, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent)


def _file_info(
    files: Mapping[str, Path], catalog: Catalog | None
) -> tuple[str | None, dict[str, dict[str, Any]]]:
    """La colección del dominio y, de cada fichero, su ruta y su huella.

    Las rutas de los ficheros del catálogo son relativas a él; el problema de una colección
    lleva además su identificador (``p01``).
    """
    if catalog is None:
        try:
            catalog = Catalog()
        except CatalogError:
            catalog = None
    collection = None
    info: dict[str, dict[str, Any]] = {"domain": {}, "problem": {}, "plan": {}}
    for kind, path in files.items():
        entry: dict[str, Any] = {"file": str(path)}
        resolved = path.resolve()
        if catalog is not None and resolved.is_relative_to(catalog.root):
            entry["file"] = resolved.relative_to(catalog.root).as_posix()
            directory = resolved.parent.relative_to(catalog.root).as_posix()
            if directory in catalog.collections:
                if kind == "domain":
                    collection = directory
                elif kind == "problem" and not is_domain_file(resolved):
                    entry["id"] = resolved.stem
        entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        info[kind] = entry
    if collection is None:
        info["problem"].pop("id", None)
    return collection, info


def generate_trace(
    domain_path: Path,
    problem_path: Path,
    plan_path: Path,
    *,
    degradation: Degradation | None = None,
    world: str = "closed",
    universe: str = "dynamic",
    provenance: Provenance | None = None,
    max_atoms: int = MAX_ATOMS,
    validate_with_val: bool = False,
    catalog: Catalog | None = None,
) -> dict[str, Any]:
    """Lee el dominio, el problema y el plan, ejecuta el plan y devuelve su traza."""
    try:
        domain = read_domain(read_text(domain_path))
        problem = read_problem(read_text(problem_path))
        steps = parse_plan(plan_path.read_text(encoding="utf-8", errors="replace"))
    except (PDDLSyntaxError, PDDLStructureError, OSError) as error:
        raise TraceError(str(error)) from error
    execution = execute(domain, problem, steps)
    val = None
    if validate_with_val:
        from pddldomains.val import validate

        val = validate(domain_path, problem_path, plan_path).verdict
    return build_trace(
        execution,
        degradation or Degradation(),
        world=world,
        universe=universe,
        provenance=provenance,
        files={"domain": domain_path, "problem": problem_path, "plan": plan_path},
        max_atoms=max_atoms,
        val=val,
        catalog=catalog,
    )
