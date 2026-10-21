"""Requisitos que usa de verdad un dominio o un problema, y los tipos que se deducen de ellos.

Las reglas son las de un modo estricto (toda construcción necesita su requisito) y siguen la
gramática de PDDL 2.1:

* sección ``:types`` o listas con tipos → ``:typing``;
* ``(not <átomo>)`` en una fórmula → ``:negative-preconditions``;
* ``(not <fórmula compuesta>)``, ``or`` e ``imply`` → ``:disjunctive-preconditions``;
* ``exists`` → ``:existential-preconditions``; ``forall`` en una fórmula →
  ``:universal-preconditions``;
* ``=`` entre términos → ``:equality``;
* ``forall`` y ``when`` en un efecto → ``:conditional-effects``;
* funciones, comparaciones, efectos numéricos, valores iniciales y métrica →
  ``:numeric-fluents``. Lo que encaja en el perfil de ``:action-costs`` (declarar
  funciones y darles valor inicial, ``(increase (total-cost) <número o función>)`` y
  ``(:metric minimize (total-cost))``) se anota como ``:action-costs``, que también queda
  cubierto si se declara ``:numeric-fluents``;
* acciones durativas → ``:durative-actions``; restricciones de duración con ``<=``/``>=``,
  varias o en ``(at start|end ...)`` → ``:duration-inequalities``; efectos con ``#t`` en
  una acción durativa → ``:continuous-effects``;
* reglas ``:derived`` → ``:derived-predicates``;
* ``(at <número> <literal>)`` en ``:init`` → ``:timed-initial-literals``;
* funciones con tipo de objeto, o ``assign`` de un objeto → ``:object-fluents``;
* ``:constraints`` y sus operadores modales → ``:constraints``;
* ``preference`` e ``is-violated`` → ``:preferences``. Una métrica que solo usa números,
  aritmética e ``is-violated`` no necesita además ``:numeric-fluents``;
* procesos y eventos → ``:time``. Los efectos continuos de un proceso no necesitan
  ``:continuous-effects``, pero sí ``:numeric-fluents``.

``(not <átomo>)`` en un efecto (un borrado) y en ``:init`` no necesita nada.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from pddldomains.i18n import _
from pddldomains.pddl import Domain, Problem, TypedName
from pddldomains.sexpr import SExpr, SList, is_number, to_text

#: Requisito que se supone cuando no se declara ``:requirements``.
DEFAULT_REQUIREMENT = ":strips"

#: Todos los requisitos que existen en las versiones de PDDL.
KNOWN_REQUIREMENTS: frozenset[str] = frozenset(
    {
        # PDDL 1.2
        ":strips",
        ":typing",
        ":negative-preconditions",
        ":disjunctive-preconditions",
        ":equality",
        ":existential-preconditions",
        ":universal-preconditions",
        ":quantified-preconditions",
        ":conditional-effects",
        ":action-expansions",
        ":foreach-expansions",
        ":dag-expansions",
        ":domain-axioms",
        ":subgoals-through-axioms",
        ":safety-constraints",
        ":expression-evaluation",
        ":fluents",
        ":open-world",
        ":true-negation",
        ":adl",
        ":ucpop",
        # PDDL 2.1
        ":numeric-fluents",
        ":durative-actions",
        ":duration-inequalities",
        ":continuous-effects",
        # PDDL 2.2
        ":derived-predicates",
        ":timed-initial-literals",
        # PDDL+
        ":time",
        # PDDL 3 y 3.1
        ":constraints",
        ":preferences",
        ":action-costs",
        ":object-fluents",
    }
)

#: Requisitos que equivalen a un conjunto de otros.
REQUIREMENT_EXPANSIONS: dict[str, frozenset[str]] = {
    ":quantified-preconditions": frozenset(
        {":existential-preconditions", ":universal-preconditions"}
    ),
    ":adl": frozenset(
        {
            ":strips",
            ":typing",
            ":negative-preconditions",
            ":disjunctive-preconditions",
            ":equality",
            ":existential-preconditions",
            ":universal-preconditions",
            ":quantified-preconditions",
            ":conditional-effects",
        }
    ),
    ":fluents": frozenset({":numeric-fluents", ":object-fluents"}),
}

#: Requisitos de lógica que hacen que un dominio clásico sea ADL y no STRIPS.
ADL_REQUIREMENTS = frozenset(
    {
        ":negative-preconditions",
        ":disjunctive-preconditions",
        ":equality",
        ":existential-preconditions",
        ":universal-preconditions",
        ":conditional-effects",
    }
)

#: Tipos (etiquetas) de un dominio, en el orden en que se muestran, con su descripción (que
#: se traduce al mostrarla).
TAGS: dict[str, str] = {
    "classical": "clásico: sin números (salvo costes), tiempo, PDDL 3 ni PDDL+",
    "strips": "clásico solo con STRIPS (y tipos)",
    "adl": "clásico con negación, disyunción, igualdad, cuantificadores o efectos condicionales",
    "costs": "costes de acción (:action-costs) sin más números",
    "numeric": "fluentes numéricos (PDDL 2.1)",
    "temporal": "acciones durativas (PDDL 2.1)",
    "continuous": "efectos continuos en acciones durativas",
    "derived": "predicados derivados (PDDL 2.2)",
    "til": "literales iniciales temporizados (PDDL 2.2)",
    "preferences": "preferencias (PDDL 3)",
    "constraints": "restricciones de trayectoria (PDDL 3)",
    "object-fluents": "fluentes de objetos (PDDL 3.1)",
    "pddlplus": "procesos y eventos (PDDL+)",
}

_COMPARISONS = frozenset({"<", ">", "<=", ">=", "="})
_ARITHMETIC = frozenset({"+", "-", "*", "/"})
_NUMERIC_EFFECTS = frozenset({"increase", "decrease", "assign", "scale-up", "scale-down"})
#: Operadores modales de las restricciones y el número de argumentos que van delante de la
#: primera fórmula (los tiempos).
_MODAL = {
    "always": 0,
    "sometime": 0,
    "at-most-once": 0,
    "sometime-after": 0,
    "sometime-before": 0,
    "within": 1,
    "always-within": 1,
    "hold-during": 2,
    "hold-after": 1,
}


@dataclass(frozen=True)
class RequirementUse:
    """Una construcción que necesita un requisito.

    Attributes:
        requirement: el requisito (``":typing"``…).
        construct: la construcción, en una línea, para los mensajes.
        offset: su posición en el fichero.
    """

    requirement: str
    construct: str
    offset: int


def expand_requirements(requirements: Iterable[str]) -> frozenset[str]:
    """Los requisitos con todos los que implican; :data:`DEFAULT_REQUIREMENT` si no hay."""
    pending = list(requirements) or [DEFAULT_REQUIREMENT]
    result: set[str] = set()
    while pending:
        requirement = pending.pop()
        if requirement not in result:
            result.add(requirement)
            pending.extend(REQUIREMENT_EXPANSIONS.get(requirement, ()))
    return frozenset(result)


def is_covered(requirement: str, declared: frozenset[str]) -> bool:
    """Indica si un requisito usado queda cubierto por los declarados (ya expandidos)."""
    if requirement in declared:
        return True
    return requirement == ":action-costs" and ":numeric-fluents" in declared


def undeclared(uses: Iterable[RequirementUse], declared: Iterable[str]) -> list[RequirementUse]:
    """El primer uso de cada requisito que no cubren los declarados."""
    expanded = expand_requirements(declared)
    seen: set[str] = set()
    result = []
    for use in uses:
        if use.requirement not in seen and not is_covered(use.requirement, expanded):
            seen.add(use.requirement)
            result.append(use)
    return result


def used_requirements(uses: Iterable[RequirementUse]) -> frozenset[str]:
    """Los requisitos usados (ver :func:`normalize_used`)."""
    return normalize_used(use.requirement for use in uses)


def normalize_used(requirements: Iterable[str]) -> frozenset[str]:
    """Quita ``:action-costs`` de unos requisitos usados si ya se usan fluentes numéricos."""
    used = set(requirements)
    if ":numeric-fluents" in used:
        used.discard(":action-costs")
    return frozenset(used)


def classify(used: frozenset[str]) -> list[str]:
    """Los tipos (:data:`TAGS`) que corresponden a unos requisitos usados."""
    numeric = ":numeric-fluents" in used
    special = {
        ":numeric-fluents",
        ":durative-actions",
        ":timed-initial-literals",
        ":preferences",
        ":constraints",
        ":object-fluents",
        ":time",
    }
    tags = []
    if not used & special:
        tags.append("classical")
        tags.append("adl" if used & ADL_REQUIREMENTS else "strips")
    flags = {
        "costs": ":action-costs" in used and not numeric,
        "numeric": numeric,
        "temporal": ":durative-actions" in used,
        "continuous": ":continuous-effects" in used,
        "derived": ":derived-predicates" in used,
        "til": ":timed-initial-literals" in used,
        "preferences": ":preferences" in used,
        "constraints": ":constraints" in used,
        "object-fluents": ":object-fluents" in used,
        "pddlplus": ":time" in used,
    }
    tags.extend(tag for tag, flag in flags.items() if flag)
    return tags


@dataclass(frozen=True)
class Level:
    """Un nivel de la escala de versiones de PDDL.

    Attributes:
        number: el número del nivel (1 a 6).
        name: la versión de PDDL (``"PDDL 2.1"``…).
        description: lo que añade al nivel anterior.
        requirements: los requisitos que llevan un dominio a este nivel.
    """

    number: int
    name: str
    description: str
    requirements: frozenset[str]

    def __str__(self) -> str:
        return f"{self.number} ({self.name})"


#: La escala de versiones, de menos a más. Un dominio está en el nivel más alto de los
#: requisitos que usa, así que un planificador que soporta hasta el nivel N tiene que poder
#: con todos los dominios de los niveles 1 a N. Tres requisitos no van en el nivel de la
#: versión que los introdujo: ``:typing`` en el 2, con el resto de ADL (el 1 es STRIPS puro);
#: ``:action-costs`` (PDDL 3.1) en el 3, porque es un caso particular de los fluentes
#: numéricos; y ``:object-fluents`` (PDDL 3.1) en el 5, con el resto de PDDL 3.
LEVELS: tuple[Level, ...] = (
    Level(1, "STRIPS", "STRIPS sin tipos", frozenset()),
    Level(
        2,
        "PDDL 1.2",
        "ADL: tipos, negación, disyunción, igualdad, cuantificadores y efectos condicionales",
        frozenset({":typing"}) | ADL_REQUIREMENTS,
    ),
    Level(
        3,
        "PDDL 2.1",
        "fluentes numéricos (y costes de acción) y acciones durativas",
        frozenset(
            {
                ":numeric-fluents",
                ":action-costs",
                ":durative-actions",
                ":duration-inequalities",
                ":continuous-effects",
            }
        ),
    ),
    Level(
        4,
        "PDDL 2.2",
        "predicados derivados y literales iniciales temporizados",
        frozenset({":derived-predicates", ":timed-initial-literals"}),
    ),
    Level(
        5,
        "PDDL 3",
        "preferencias, restricciones de trayectoria y fluentes de objetos",
        frozenset({":preferences", ":constraints", ":object-fluents"}),
    ),
    Level(6, "PDDL+", "procesos y eventos", frozenset({":time"})),
)

_LEVEL_ALIASES = {"adl": 2, "pddlplus": 6, "pddl+": 6, "plus": 6}


def level_of(used: frozenset[str]) -> Level:
    """El nivel de unos requisitos usados: el más alto de los que aparecen."""
    return max(
        (level for level in LEVELS if level.requirements & used),
        key=lambda lv: lv.number,
        default=LEVELS[0],
    )


def level_reasons(used: frozenset[str]) -> list[str]:
    """Los requisitos usados que llevan al nivel de :func:`level_of`."""
    return sorted(level_of(used).requirements & used)


def parse_level(value: int | str) -> Level:
    """Un nivel por su número (``3``) o su nombre (``"PDDL 2.1"``, ``"2.1"``, ``"strips"``,
    ``"adl"``, ``"pddl+"``)."""
    text = str(value).strip().lower()
    if text.isdigit() and 1 <= int(text) <= len(LEVELS):
        return LEVELS[int(text) - 1]
    if text in _LEVEL_ALIASES:
        return LEVELS[_LEVEL_ALIASES[text] - 1]
    for level in LEVELS:
        name = level.name.lower()
        if text in (name, name.removeprefix("pddl ")):
            return level
    names = ", ".join(f"{lv.number} ({lv.name})" for lv in LEVELS)
    raise ValueError(
        _("nivel desconocido '{value}' (los niveles son {names})", value=value, names=names)
    )


def domain_uses(domain: Domain) -> list[RequirementUse]:
    """Los usos de requisitos de un dominio, en orden de aparición."""
    walker = _Walker(domain)
    walker.domain()
    return walker.uses


def problem_uses(problem: Problem, domain: Domain) -> list[RequirementUse]:
    """Los usos de requisitos de un problema (con su dominio, para conocer las funciones)."""
    walker = _Walker(domain)
    walker.problem(problem)
    return walker.uses


class _Walker:
    """Recorre las secciones y anota en ``uses`` cada construcción que necesita un requisito."""

    def __init__(self, domain: Domain) -> None:
        self.domain_ = domain
        self.uses: list[RequirementUse] = []
        self.function_types = domain.function_types()
        self.object_functions = {
            name for name, type_ in self.function_types.items() if type_ != "number"
        }

    def use(self, requirement: str, node: SExpr, offset: int) -> None:
        position = node.offset if isinstance(node, SList) else offset
        self.uses.append(RequirementUse(requirement, to_text(node, 60), position))

    # --- Declaraciones -------------------------------------------------------------------

    def typed(self, names: Iterable[TypedName], offset: int) -> None:
        for typed in names:
            if typed.explicit:
                self.use(":typing", f"{typed.name} - {_type_text(typed.type)}", typed.offset)
                return

    def domain(self) -> None:
        domain = self.domain_
        if domain.has_types:
            self.use(":typing", "(:types ...)", domain.section_offsets.get(":types", 0))
        self.typed(domain.constants, domain.offset)
        for signature in (*domain.predicates, *domain.functions):
            self.typed(signature.parameters, signature.offset)
        for function in domain.functions:
            if function.type != "number":
                self.use(":object-fluents", f"({function.name}) - {function.type}", function.offset)
            else:
                # Declarar funciones cabe en el perfil de :action-costs.
                self.use(":action-costs", f"({function.name})", function.offset)
        for operator in domain.operators:
            self.typed(operator.parameters, operator.node.offset)
            offset = operator.node.offset
            if operator.kind == "durative-action":
                self.use(":durative-actions", f"(:durative-action {operator.name} ...)", offset)
                if ":duration" in operator.fields:
                    self.duration(operator.fields[":duration"], offset)
                if ":condition" in operator.fields:
                    self.formula(operator.fields[":condition"], offset)
                if ":effect" in operator.fields:
                    self.effect(operator.fields[":effect"], offset, durative=True)
            else:
                if operator.kind in ("process", "event"):
                    self.use(":time", f"(:{operator.kind} {operator.name} ...)", offset)
                if ":precondition" in operator.fields:
                    self.formula(operator.fields[":precondition"], offset)
                if ":effect" in operator.fields:
                    self.effect(
                        operator.fields[":effect"], offset, process=operator.kind == "process"
                    )
        for head, body in domain.derived:
            self.use(":derived-predicates", f"(:derived {to_text(head, 40)} ...)", head.offset)
            self.formula(body, head.offset)
        if domain.constraints is not None:
            self.constraints(domain.constraints, domain.section_offsets.get(":constraints", 0))

    def problem(self, problem: Problem) -> None:
        self.typed(problem.objects, problem.offset)
        for fact in problem.init or ():
            self.init_fact(fact, problem.offset)
        if problem.goal is not None:
            self.formula(problem.goal, problem.section_offsets.get(":goal", problem.offset))
        if problem.constraints is not None:
            self.constraints(
                problem.constraints, problem.section_offsets.get(":constraints", problem.offset)
            )
        if problem.metric is not None:
            self.metric(problem.metric[1], problem.section_offsets.get(":metric", problem.offset))

    def init_fact(self, fact: SExpr, offset: int) -> None:
        if not isinstance(fact, SList) or not fact:
            return
        head = fact[0]
        if head == "=" and len(fact) == 3:
            target, value = fact[1], fact[2]
            name = target[0] if isinstance(target, SList) and target else target
            if name in self.object_functions or not (is_number(value) or isinstance(value, SList)):
                self.use(":object-fluents", fact, offset)
            else:
                self.use(":action-costs", fact, offset)
        elif head == "at" and len(fact) == 3 and is_number(fact[1]):
            self.use(":timed-initial-literals", fact, offset)

    # --- Fórmulas ------------------------------------------------------------------------

    def formula(self, node: SExpr, offset: int, *, constraint: bool = False) -> None:
        if not isinstance(node, SList) or not node:
            return
        head = node[0]
        args = node[1:]
        if head == "and":
            for arg in args:
                self.formula(arg, offset, constraint=constraint)
        elif head in ("or", "imply"):
            self.use(":disjunctive-preconditions", node, offset)
            for arg in args:
                self.formula(arg, offset, constraint=constraint)
        elif head == "not":
            argument = args[0] if args else None
            if isinstance(argument, SList) and self.is_atomic(argument):
                self.use(":negative-preconditions", node, offset)
            else:
                self.use(":disjunctive-preconditions", node, offset)
            if argument is not None:
                self.formula(argument, offset, constraint=constraint)
        elif head in ("exists", "forall") and len(node) == 3:
            requirement = (
                ":existential-preconditions" if head == "exists" else (":universal-preconditions")
            )
            self.use(requirement, node, offset)
            self.variables(node[1], offset)
            self.formula(node[2], offset, constraint=constraint)
        elif head == "preference":
            self.use(":preferences", node, offset)
            if args:
                self.formula(args[-1], offset, constraint=constraint)
        elif _is_timed(node):
            if constraint and node[1] == "end":
                self.use(":constraints", node, offset)
            self.formula(node[2], offset, constraint=constraint)
        elif constraint and head in _MODAL:
            self.use(":constraints", node, offset)
            for arg in args[_MODAL[head] :]:
                self.formula(arg, offset, constraint=True)
            for time in args[: _MODAL[head]]:
                self.expression(time, offset)
        elif head in _COMPARISONS and len(node) == 3:
            if head == "=" and not any(self.is_numeric_term(a) for a in args):
                self.use(":equality", node, offset)
            elif any(isinstance(a, SList) and a and a[0] in self.object_functions for a in args):
                self.use(":object-fluents", node, offset)
            else:
                self.use(":numeric-fluents", node, offset)
                for arg in args:
                    self.expression(arg, offset)

    def constraints(self, node: SExpr, offset: int) -> None:
        if isinstance(node, SList) and node == ["and"]:
            return  # (:constraints (and)) vacío: no restringe nada.
        self.use(":constraints", "(:constraints ...)", offset)
        self.formula(node, offset, constraint=True)

    def is_atomic(self, node: SList) -> bool:
        """Si ``node`` es un átomo (un predicado o una igualdad), no una fórmula compuesta."""
        head = node[0] if node else None
        return head not in {"and", "or", "not", "imply", "exists", "forall", "preference"} and not (
            head in _COMPARISONS and head != "=" and len(node) == 3
        )

    def is_numeric_term(self, term: SExpr) -> bool:
        if isinstance(term, SList):
            return not (term and term[0] in self.object_functions)
        return is_number(term) or term in self.function_types

    def variables(self, node: SExpr, offset: int) -> None:
        if isinstance(node, SList):
            from pddldomains.pddl import typed_list

            self.typed(typed_list(list(node), [], node.offset), offset)

    # --- Efectos -------------------------------------------------------------------------

    def effect(
        self, node: SExpr, offset: int, *, durative: bool = False, process: bool = False
    ) -> None:
        if not isinstance(node, SList) or not node:
            return
        head = node[0]
        if head == "and":
            for arg in node[1:]:
                self.effect(arg, offset, durative=durative, process=process)
        elif head == "forall" and len(node) == 3:
            self.use(":conditional-effects", node, offset)
            self.variables(node[1], offset)
            self.effect(node[2], offset, durative=durative, process=process)
        elif head == "when" and len(node) == 3:
            self.use(":conditional-effects", node, offset)
            self.formula(node[1], offset)
            self.effect(node[2], offset, durative=durative, process=process)
        elif _is_timed(node):
            self.effect(node[2], offset, durative=durative, process=process)
        elif head in _NUMERIC_EFFECTS and len(node) == 3:
            self.numeric_effect(node, offset, durative=durative, process=process)

    def numeric_effect(self, node: SList, offset: int, *, durative: bool, process: bool) -> None:
        head, target, value = node[0], node[1], node[2]
        target_name = target[0] if isinstance(target, SList) and target else target
        if _mentions(value, "#t"):
            if durative and not process:
                self.use(":continuous-effects", node, offset)
            self.use(":numeric-fluents", node, offset)
        elif target_name in self.object_functions or value == "undefined":
            self.use(":object-fluents", node, offset)
        elif (
            head == "increase"
            and target_name == "total-cost"
            and (is_number(value) or self.is_function_term(value))
        ):
            self.use(":action-costs", node, offset)
        else:
            self.use(":numeric-fluents", node, offset)
        self.expression(value, offset)

    def is_function_term(self, node: SExpr) -> bool:
        """Si ``node`` es una función aplicada a variables u objetos (no una expresión)."""
        return (
            isinstance(node, SList)
            and bool(node)
            and node[0] in self.function_types
            and all(isinstance(a, str) for a in node[1:])
        )

    # --- Expresiones, duración y métrica ---------------------------------------------------

    def expression(self, node: SExpr, offset: int) -> None:
        if not isinstance(node, SList) or not node:
            return
        if node[0] == "is-violated":
            self.use(":preferences", node, offset)
        for arg in node[1:]:
            self.expression(arg, offset)

    def duration(self, node: SExpr, offset: int) -> None:
        if not isinstance(node, SList) or not node:
            return
        head = node[0]
        if head == "and":
            if len(node) > 2:
                self.use(":duration-inequalities", node, offset)
            for arg in node[1:]:
                self.duration(arg, offset)
        elif _is_timed(node):
            self.use(":duration-inequalities", node, offset)
            self.duration(node[2], offset)
        elif head in ("<=", ">=", "=") and len(node) == 3:
            if head != "=":
                self.use(":duration-inequalities", node, offset)
            value = node[2]
            if not is_number(value):
                self.use(":numeric-fluents", node, offset)

    def metric(self, node: SExpr, offset: int) -> None:
        if isinstance(node, SList) and node == ["total-cost"]:
            self.use(":action-costs", "(:metric minimize (total-cost))", offset)
            return
        if _only_preferences(node):
            self.use(":preferences", node, offset)
            return
        self.use(":numeric-fluents", node, offset)
        self.expression(node, offset)


def _is_timed(node: SList) -> bool:
    """``(at start φ)``, ``(at end φ)`` u ``(over all φ)``."""
    return (
        len(node) == 3
        and isinstance(node[2], SList)
        and (
            (node[0] == "at" and node[1] in ("start", "end"))
            or (node[0] == "over" and node[1] == "all")
        )
    )


def _mentions(node: SExpr, token: str) -> bool:
    if isinstance(node, str):
        return node == token
    return any(_mentions(child, token) for child in node)


def _only_preferences(node: SExpr) -> bool:
    """Si una expresión solo usa números, aritmética e ``is-violated``."""
    if isinstance(node, str):
        return is_number(node)
    if not node:
        return False
    if node[0] == "is-violated":
        return True
    return node[0] in _ARITHMETIC and all(_only_preferences(arg) for arg in node[1:])


def _type_text(type_: str | tuple[str, ...]) -> str:
    return type_ if isinstance(type_, str) else "(either " + " ".join(type_) + ")"
