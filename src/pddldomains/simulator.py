"""Simulador de planes secuenciales: ejecuta acciones de un dominio sobre estados.

Admite STRIPS y ADL (tipos, negación, disyunción, cuantificadores, igualdad y efectos
condicionales), predicados derivados (estratificados), fluentes numéricos (comparaciones,
expresiones aritméticas y los efectos ``increase``, ``decrease``, ``assign``, ``scale-up`` y
``scale-down``) y costes de acción. Las preferencias no afectan a la aplicabilidad (se
toman como ciertas) y las restricciones de trayectoria no se comprueban.

No admite acciones durativas, procesos, eventos, literales iniciales temporizados ni
fluentes de objetos: :class:`Unsupported`.

Un estado (:class:`State`) son los átomos básicos ciertos, los derivados que se deducen de
ellos y los valores de los fluentes numéricos. Los efectos de una acción se calculan sobre
el estado de antes (también los valores numéricos) y se aplican a la vez: primero los
borrados y después las adiciones, como en PDDL.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from itertools import product

from pddldomains.i18n import _
from pddldomains.pddl import Domain, Operator, Problem, TypedName, typed_list
from pddldomains.sexpr import SExpr, SList, is_number, to_text

type Atom = tuple[str, ...]
type Term = tuple[str, ...]
type Binding = dict[str, str]

#: Efectos numéricos.
NUMERIC_EFFECTS = frozenset({"increase", "decrease", "assign", "scale-up", "scale-down"})
_COMPARISONS = frozenset({"<", ">", "<=", ">=", "="})
_ARITHMETIC = frozenset({"+", "-", "*", "/"})
_CONNECTIVES = frozenset({"and", "or", "not", "imply", "exists", "forall", "preference"})


class SimulationError(Exception):
    """Algo que impide seguir ejecutando: un valor indefinido, una división entre cero…"""


class Unsupported(SimulationError):
    """El dominio, el problema o el plan usan algo que el simulador no admite."""


@dataclass(frozen=True)
class State:
    """Un estado: átomos básicos, átomos derivados y valores numéricos.

    Attributes:
        atoms: átomos básicos ciertos.
        derived: átomos de predicados derivados ciertos (se deducen de los básicos).
        values: valor de cada fluente numérico definido (``("fuel", "plane1")`` → 100.0).
    """

    atoms: frozenset[Atom]
    derived: frozenset[Atom]
    values: Mapping[Term, float]

    @property
    def facts(self) -> frozenset[Atom]:
        """Todos los átomos ciertos, básicos y derivados."""
        return self.atoms | self.derived

    def key(self) -> tuple[frozenset[Atom], tuple[tuple[Term, float], ...]]:
        """Una clave para comparar estados."""
        return self.atoms, tuple(sorted(self.values.items()))


def atom_text(atom: Atom) -> str:
    """``("on", "a", "b")`` → ``"(on a b)"``."""
    return "(" + " ".join(atom) + ")"


def _type_names(type_: str | tuple[str, ...]) -> tuple[str, ...]:
    return type_ if isinstance(type_, tuple) else (type_,)


class Simulator:
    """Ejecuta acciones de un dominio sobre los estados de un problema."""

    def __init__(self, domain: Domain, problem: Problem) -> None:
        self.domain = domain
        self.problem = problem
        for operator in domain.operators:
            if operator.kind != "action":
                raise Unsupported(
                    _(
                        "el simulador no admite '{kind}' ('{name}'): solo acciones instantáneas",
                        kind=operator.kind,
                        name=operator.name,
                    )
                )
        self.operators = {operator.name: operator for operator in domain.operators}
        for function in domain.functions:
            if function.type != "number":
                raise Unsupported(
                    _("el simulador no admite fluentes de objetos ('{name}')", name=function.name)
                )
        self.functions = {function.name for function in domain.functions}
        parents: dict[str, set[str]] = {}
        for typed in domain.types:
            parents.setdefault(typed.name, set()).update(_type_names(typed.type))
        self._parents = parents
        declared = [*domain.constants, *problem.objects]
        #: El tipo declarado de cada objeto y constante.
        self.object_types: dict[str, str | tuple[str, ...]] = {o.name: o.type for o in declared}
        self._objects: dict[str, set[str]] = {}  # tipo -> objetos (con los subtipos)
        for typed in declared:
            for type_ in self.ancestors(typed.type):
                self._objects.setdefault(type_, set()).add(typed.name)
        self.all_objects = sorted(self.object_types)
        self.derived_predicates = {
            head[0] for head, _body in domain.derived if head and isinstance(head[0], str)
        }
        #: Los predicados que cambian las acciones (los demás, salvo los derivados, son
        #: estáticos).
        self.fluent_predicates: set[str] = set()
        for operator in domain.operators:
            _effect_predicates(operator.fields.get(":effect", SList(0)), self.fluent_predicates)
        self._strata = self._stratify()

    # --- Tipos y objetos -------------------------------------------------------------------

    def ancestors(self, type_: str | tuple[str, ...]) -> set[str]:
        """El tipo (o tipos, con ``either``) y todos sus antecesores, ``object`` incluido."""
        pending = list(_type_names(type_))
        seen = {"object"}
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current)
                pending.extend(self._parents.get(current, ()))
        return seen

    def objects_of(self, type_: str | tuple[str, ...]) -> list[str]:
        """Los objetos (y constantes) de un tipo, ordenados."""
        if type_ == "object":
            return self.all_objects
        return sorted(set().union(*(self._objects.get(t, set()) for t in _type_names(type_))))

    def assignments(self, variables: list[TypedName], binding: Binding) -> Iterator[Binding]:
        """Cada forma de dar valor a ``variables`` (según su tipo), sobre ``binding``."""
        domains = [self.objects_of(variable.type) for variable in variables]
        for values in product(*domains):
            yield {**binding, **{v.name: value for v, value in zip(variables, values, strict=True)}}

    # --- Estados ---------------------------------------------------------------------------

    def initial_state(self) -> State:
        """El estado inicial del problema."""
        atoms: set[Atom] = set()
        values: dict[Term, float] = {}
        for fact in self.problem.init or ():
            if not isinstance(fact, SList) or not fact:
                continue
            head = fact[0]
            if head == "=" and len(fact) == 3:
                target, value = fact[1], fact[2]
                if not isinstance(target, SList) or not is_number(value):
                    raise Unsupported(_("valor inicial no admitido: {fact}", fact=to_text(fact)))
                assert isinstance(value, str)
                values[self.term_key(target, {})] = float(value)
            elif head == "at" and len(fact) == 3 and is_number(fact[1]):
                raise Unsupported(_("el simulador no admite literales iniciales temporizados"))
            elif head != "not":
                atoms.add(self.ground(fact, {}))
        return self.make_state(frozenset(atoms), values)

    def make_state(self, atoms: frozenset[Atom], values: Mapping[Term, float]) -> State:
        """Un estado con sus átomos derivados."""
        return State(atoms, self._derive(atoms, values), dict(values))

    # --- Evaluación ------------------------------------------------------------------------

    @staticmethod
    def ground(node: SList, binding: Binding) -> Atom:
        """El átomo de ``node`` con las variables sustituidas."""
        head = node[0]
        assert isinstance(head, str)
        return (head, *(binding.get(a, a) if isinstance(a, str) else to_text(a) for a in node[1:]))

    def term_key(self, node: SList, binding: Binding) -> Term:
        """La clave de un término de función (``(fuel ?p)`` → ``("fuel", "plane1")``)."""
        name = node[0] if node else None
        if not isinstance(name, str) or (name not in self.functions and name != "total-cost"):
            raise SimulationError(_("función desconocida: {node}", node=to_text(node)))
        return self.ground(node, binding)

    def holds(self, node: SExpr, binding: Binding, state: State) -> bool:
        """Si la fórmula ``node`` se cumple en ``state``."""
        if not isinstance(node, SList):
            raise Unsupported(_("fórmula no admitida: {node}", node=node))
        if not node:
            return True
        head = node[0]
        if head == "and":
            return all(self.holds(child, binding, state) for child in node[1:])
        if head == "or":
            return any(self.holds(child, binding, state) for child in node[1:])
        if head == "not":
            return not self.holds(node[1], binding, state)
        if head == "imply":
            return not self.holds(node[1], binding, state) or self.holds(node[2], binding, state)
        if head in ("exists", "forall") and len(node) == 3:
            variables = typed_list(list(node[1]), [], 0) if isinstance(node[1], SList) else []
            checks = (self.holds(node[2], b, state) for b in self.assignments(variables, binding))
            return any(checks) if head == "exists" else all(checks)
        if head == "preference":
            return True  # una preferencia no condiciona la aplicabilidad ni el objetivo
        if head in _COMPARISONS and len(node) == 3:
            left, right = node[1], node[2]
            if head == "=" and self._is_object_term(left) and self._is_object_term(right):
                assert isinstance(left, str) and isinstance(right, str)
                return binding.get(left, left) == binding.get(right, right)
            return _compare(
                head, self.evaluate(left, binding, state), self.evaluate(right, binding, state)
            )
        if head in ("at", "over") and len(node) == 3 and isinstance(node[2], SList):
            raise Unsupported(_("condiciones temporales: {node}", node=to_text(node)))
        atom = self.ground(node, binding)
        return atom in (state.derived if atom[0] in self.derived_predicates else state.atoms)

    def _is_object_term(self, term: SExpr) -> bool:
        return isinstance(term, str) and not is_number(term) and term not in self.functions

    def evaluate(self, node: SExpr, binding: Binding, state: State) -> float:
        """El valor de la expresión numérica ``node`` en ``state``."""
        if isinstance(node, str):
            if is_number(node):
                return float(node)
            if node in self.functions:  # función sin argumentos escrita sin paréntesis
                return self._value(state.values, (node,))
            raise SimulationError(_("expresión no válida: {node}", node=node))
        if not node:
            raise SimulationError(_("expresión vacía"))
        head = node[0]
        args = (
            [self.evaluate(arg, binding, state) for arg in node[1:]] if head in _ARITHMETIC else []
        )
        if head == "+":
            return sum(args)
        if head == "*":
            result = 1.0
            for value in args:
                result *= value
            return result
        if head == "-":
            return -args[0] if len(args) == 1 else args[0] - sum(args[1:])
        if head == "/":
            if len(args) != 2:
                raise SimulationError(_("división con {count} argumentos", count=len(args)))
            if args[1] == 0:
                raise SimulationError(_("división entre cero: {node}", node=to_text(node)))
            return args[0] / args[1]
        if head in ("total-time", "?duration", "#t"):
            raise Unsupported(_("expresión temporal: {node}", node=to_text(node)))
        return self._value(state.values, self.term_key(node, binding))

    @staticmethod
    def _value(values: Mapping[Term, float], key: Term) -> float:
        if key not in values:
            raise SimulationError(
                _(
                    "el fluente {term} no tiene valor (no se le dio valor inicial)",
                    term=atom_text(key),
                )
            )
        return values[key]

    # --- Acciones --------------------------------------------------------------------------

    def action(self, name: str, arguments: list[str]) -> tuple[Operator, Binding]:
        """El operador y los argumentos de una acción del plan, comprobados."""
        operator = self.operators.get(name)
        if operator is None:
            raise SimulationError(_("acción desconocida '{name}'", name=name))
        if len(arguments) != len(operator.parameters):
            raise SimulationError(
                _(
                    "'{name}' tiene {expected} parámetros y se le dan {count}",
                    name=name,
                    expected=len(operator.parameters),
                    count=len(arguments),
                )
            )
        binding: Binding = {}
        for parameter, argument in zip(operator.parameters, arguments, strict=True):
            if argument not in self.object_types:
                raise SimulationError(
                    _("objeto desconocido '{name}' en '{action}'", name=argument, action=name)
                )
            if not self.ancestors(self.object_types[argument]) & set(_type_names(parameter.type)):
                raise SimulationError(
                    _(
                        "'{name}' no es de tipo {type} (parámetro {parameter} de '{action}')",
                        name=argument,
                        type=" | ".join(_type_names(parameter.type)),
                        parameter=parameter.name,
                        action=name,
                    )
                )
            binding[parameter.name] = argument
        return operator, binding

    def applicable(self, operator: Operator, binding: Binding, state: State) -> bool:
        """Si la precondición de la acción se cumple en ``state``."""
        return self.holds(operator.fields.get(":precondition", SList(0)), binding, state)

    def unsatisfied(self, operator: Operator, binding: Binding, state: State) -> SExpr | None:
        """La primera parte de la precondición que no se cumple (para los mensajes)."""
        precondition = operator.fields.get(":precondition", SList(0))
        parts = (
            list(precondition[1:])
            if isinstance(precondition, SList) and precondition and precondition[0] == "and"
            else [precondition]
        )
        for part in parts:
            if not self.holds(part, binding, state):
                return part
        return None

    def successor(self, operator: Operator, binding: Binding, state: State) -> State:
        """El estado que resulta de aplicar la acción (sin comprobar su precondición)."""
        adds: set[Atom] = set()
        deletes: set[Atom] = set()
        updates: list[tuple[str, Term, float]] = []
        self._effects(
            operator.fields.get(":effect", SList(0)), binding, state, adds, deletes, updates
        )
        values = dict(state.values)
        for operation, key, amount in updates:
            if operation == "assign":
                values[key] = amount
                continue
            current = self._value(values, key)
            if operation == "increase":
                values[key] = current + amount
            elif operation == "decrease":
                values[key] = current - amount
            elif operation == "scale-up":
                values[key] = current * amount
            else:
                if amount == 0:
                    raise SimulationError(_("scale-down entre cero en {term}", term=atom_text(key)))
                values[key] = current / amount
        return self.make_state((state.atoms - deletes) | adds, values)

    def _effects(
        self,
        node: SExpr,
        binding: Binding,
        state: State,
        adds: set[Atom],
        deletes: set[Atom],
        updates: list[tuple[str, Term, float]],
    ) -> None:
        if not isinstance(node, SList) or not node:
            return
        head = node[0]
        if head == "and":
            for child in node[1:]:
                self._effects(child, binding, state, adds, deletes, updates)
        elif head == "not":
            target = node[1]
            if isinstance(target, SList):
                deletes.add(self.ground(target, binding))
        elif head == "forall" and len(node) == 3:
            variables = typed_list(list(node[1]), [], 0) if isinstance(node[1], SList) else []
            for inner in self.assignments(variables, binding):
                self._effects(node[2], inner, state, adds, deletes, updates)
        elif head == "when" and len(node) == 3:
            if self.holds(node[1], binding, state):
                self._effects(node[2], binding, state, adds, deletes, updates)
        elif head in NUMERIC_EFFECTS and len(node) == 3:
            target = node[1]
            if not isinstance(target, SList):
                raise SimulationError(_("efecto numérico no válido: {node}", node=to_text(node)))
            amount = self.evaluate(node[2], binding, state)  # con los valores de antes
            assert isinstance(head, str)
            updates.append((head, self.term_key(target, binding), amount))
        elif head in ("at", "over") and len(node) == 3 and isinstance(node[2], SList):
            raise Unsupported(_("efectos temporales: {node}", node=to_text(node)))
        else:
            adds.add(self.ground(node, binding))

    # --- Predicados derivados --------------------------------------------------------------

    def _stratify(self) -> list[list[tuple[SList, SExpr]]]:
        """Las reglas ``:derived`` por estratos: un predicado que depende negativamente de otro
        derivado va en un estrato posterior."""
        if not self.domain.derived:
            return []
        dependencies: list[tuple[str, str, bool]] = []  # (cabeza, de quién depende, ¿negado?)
        for head, body in self.domain.derived:
            assert isinstance(head[0], str)
            for name, negated in _predicate_uses(body, negated=False):
                if name in self.derived_predicates:
                    dependencies.append((head[0], name, negated))
        stratum = dict.fromkeys(self.derived_predicates, 0)
        for _round in range(len(stratum) + 1):
            changed = False
            for head_name, other, negated in dependencies:
                needed = stratum[other] + (1 if negated else 0)
                if stratum[head_name] < needed:
                    stratum[head_name] = needed
                    changed = True
            if not changed:
                break
        else:
            raise Unsupported(_("los predicados derivados no son estratificables"))
        layers: list[list[tuple[SList, SExpr]]] = [
            [] for _layer in range(max(stratum.values()) + 1)
        ]
        for head, body in self.domain.derived:
            assert isinstance(head[0], str)
            layers[stratum[head[0]]].append((head, body))
        return layers

    def _derive(self, atoms: frozenset[Atom], values: Mapping[Term, float]) -> frozenset[Atom]:
        derived: set[Atom] = set()
        for layer in self._strata:
            changed = True
            while changed:
                changed = False
                current = State(atoms, frozenset(derived), values)
                for head, body in layer:
                    # La cabeza lleva tipos ((upstream ?x - device ...)): el átomo, sus variables.
                    variables = typed_list(list(head[1:]), [], 0)
                    for binding in self.assignments(variables, {}):
                        atom = (str(head[0]), *(binding[v.name] for v in variables))
                        if atom not in derived and self.holds(body, binding, current):
                            derived.add(atom)
                            changed = True
        return frozenset(derived)


def _compare(operator: SExpr, left: float, right: float) -> bool:
    if operator == "<":
        return left < right
    if operator == ">":
        return left > right
    if operator == "<=":
        return left <= right
    if operator == ">=":
        return left >= right
    return left == right


def _predicate_uses(node: SExpr, *, negated: bool) -> Iterator[tuple[str, bool]]:
    """Los predicados de una fórmula, con si aparecen negados."""
    if not isinstance(node, SList) or not node:
        return
    head = node[0]
    if head == "not":
        yield from _predicate_uses(node[1], negated=not negated)
    elif head == "imply" and len(node) == 3:
        yield from _predicate_uses(node[1], negated=not negated)
        yield from _predicate_uses(node[2], negated=negated)
    elif head in ("exists", "forall") and len(node) == 3:
        yield from _predicate_uses(node[2], negated=negated)
    elif head in _CONNECTIVES:
        for child in node[1:]:
            yield from _predicate_uses(child, negated=negated)
    elif isinstance(head, str) and head not in _COMPARISONS:
        yield head, negated


def _effect_predicates(node: SExpr, result: set[str]) -> None:
    """Añade a ``result`` los predicados que añade o borra un efecto."""
    if isinstance(node, SList) and node:
        head = node[0]
        if head in ("and", "not"):
            for child in node[1:]:
                _effect_predicates(child, result)
        elif head in ("forall", "when") and len(node) == 3:
            _effect_predicates(node[2], result)
        elif isinstance(head, str) and head not in NUMERIC_EFFECTS:
            result.add(head)
