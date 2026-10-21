"""Lectura estructural de dominios y problemas PDDL.

No es un parser completo: separa las secciones (requisitos, tipos, predicados, acciones,
``:init``, objetivo…) y lee las declaraciones, pero deja las fórmulas y los efectos como
S-expresiones para que los recorran :mod:`pddldomains.features` y :mod:`pddldomains.lint`.

Es tolerante: lo que no encaja en la gramática no aborta la lectura, sino que se anota en
``issues`` (con su posición) para que el revisor lo cuente. Solo un fichero que no es un
``(define ...)`` legible lanza :class:`PDDLStructureError`.
"""

from dataclasses import dataclass, field
from pathlib import Path

from pddldomains.i18n import _
from pddldomains.sexpr import SExpr, SList, is_number, parse

#: Palabras clave de los operadores: acciones, acciones durativas y, en PDDL+, procesos y
#: eventos.
OPERATOR_KINDS = {
    ":action": "action",
    ":durative-action": "durative-action",
    ":process": "process",
    ":event": "event",
}


class PDDLStructureError(Exception):
    """El fichero no tiene la estructura de un dominio o un problema PDDL."""

    def __init__(self, message: str, offset: int = 0) -> None:
        super().__init__(message)
        self.offset = offset


@dataclass(frozen=True)
class Issue:
    """Algo que no encaja en la gramática, encontrado al leer.

    Attributes:
        code: identificador del problema (el que usa el revisor).
        message: descripción en español.
        offset: posición en el texto.
    """

    code: str
    message: str
    offset: int


@dataclass(frozen=True)
class TypedName:
    """Un nombre de una lista con tipos (``a b - t``).

    Attributes:
        name: el nombre.
        type: su tipo (una tupla con ``either``); ``object`` si no lo tiene.
        offset: posición del nombre (o de la lista que lo contiene).
        explicit: si el tipo estaba escrito (``- t``).
    """

    name: str
    type: str | tuple[str, ...]
    offset: int
    explicit: bool = True


@dataclass(frozen=True)
class Signature:
    """Declaración de un predicado o una función.

    Attributes:
        name: nombre.
        parameters: parámetros con su tipo.
        type: tipo del valor (``"number"`` o un tipo de objeto); ``None`` en los predicados.
        offset: posición de la declaración.
    """

    name: str
    parameters: tuple[TypedName, ...]
    type: str | tuple[str, ...] | None
    offset: int


@dataclass
class Operator:
    """Una acción, acción durativa, proceso o evento.

    Attributes:
        kind: ``"action"``, ``"durative-action"``, ``"process"`` o ``"event"``.
        name: nombre.
        parameters: parámetros con su tipo.
        fields: el resto de campos (``":precondition"``, ``":effect"``, ``":condition"``,
            ``":duration"``) con su S-expresión.
        node: la S-expresión completa.
    """

    kind: str
    name: str
    parameters: list[TypedName]
    fields: dict[str, SExpr]
    node: SList


@dataclass
class Domain:
    """Un dominio PDDL leído por secciones."""

    name: str
    requirements: list[str] = field(default_factory=list)
    has_requirements: bool = False
    types: list[TypedName] = field(default_factory=list)
    has_types: bool = False
    constants: list[TypedName] = field(default_factory=list)
    predicates: list[Signature] = field(default_factory=list)
    functions: list[Signature] = field(default_factory=list)
    operators: list[Operator] = field(default_factory=list)
    derived: list[tuple[SList, SExpr]] = field(default_factory=list)
    constraints: SExpr | None = None
    issues: list[Issue] = field(default_factory=list)
    offset: int = 0
    #: Posición de cada sección (``":types"``…), para los mensajes.
    section_offsets: dict[str, int] = field(default_factory=dict)

    def function_types(self) -> dict[str, str | tuple[str, ...]]:
        """Tipo del valor de cada función declarada."""
        return {f.name: f.type or "number" for f in self.functions}


@dataclass
class Problem:
    """Un problema PDDL leído por secciones."""

    name: str
    domain_name: str = ""
    domain_offset: int = 0
    requirements: list[str] = field(default_factory=list)
    objects: list[TypedName] = field(default_factory=list)
    #: Hechos y valores iniciales; ``None`` si falta la sección ``:init``.
    init: list[SExpr] | None = None
    goal: SExpr | None = None
    constraints: SExpr | None = None
    #: Dirección (``"minimize"``/``"maximize"``) y expresión de la métrica.
    metric: tuple[str, SExpr] | None = None
    issues: list[Issue] = field(default_factory=list)
    offset: int = 0
    section_offsets: dict[str, int] = field(default_factory=dict)


def offset_of(node: SExpr, default: int) -> int:
    """Posición de ``node`` si es una lista; ``default`` si es un átomo."""
    return node.offset if isinstance(node, SList) else default


def typed_list(items: list[SExpr], issues: list[Issue], offset: int) -> list[TypedName]:
    """Lee una lista con tipos (``a b - t c - (either u v) d``).

    Los nombres sin tipo son ``object``. Los elementos pueden ser átomos o listas (las
    cabeceras de las funciones en ``:functions``); de las listas se toma la posición.

    Se anotan en ``issues`` el guion pegado al tipo (``?t -tank``, que se lee como
    ``?t - tank``), el tipo sin nombres delante (``- board``) y el guion final sin tipo.
    """
    result: list[TypedName] = []
    pending: list[tuple[str, int]] = []
    i = 0
    while i < len(items):
        item = items[i]
        position = offset_of(item, offset)
        if isinstance(item, str) and item.startswith("-") and len(item) > 1 and not is_number(item):
            issues.append(
                Issue(
                    "glued-dash",
                    _(
                        "guion pegado al tipo ('{token}'): se lee como '- {type}'",
                        token=item,
                        type=item[1:],
                    ),
                    offset,
                )
            )
            assign: SExpr | None = item[1:]
            i += 1
        elif item == "-":
            if i + 1 >= len(items):
                issues.append(
                    Issue("dash-without-type", _("guion sin tipo al final de la lista"), offset)
                )
                break
            assign = items[i + 1]
            i += 2
        else:
            name = item if isinstance(item, str) else _head(item)
            pending.append((name, position))
            i += 1
            continue
        type_ = _type_of(assign, issues, offset)
        if not pending:
            issues.append(
                Issue(
                    "type-without-names",
                    _("'- {type}' sin nombres delante", type=_type_text(type_)),
                    offset,
                )
            )
        result.extend(TypedName(name, type_, pos) for name, pos in pending)
        pending = []
    result.extend(TypedName(name, "object", pos, explicit=False) for name, pos in pending)
    return result


def _type_of(node: SExpr | None, issues: list[Issue], offset: int) -> str | tuple[str, ...]:
    if isinstance(node, str):
        return node
    if isinstance(node, SList) and node and node[0] == "either":
        return tuple(t for t in node[1:] if isinstance(t, str))
    issues.append(Issue("invalid-type", _("tipo que no es un nombre ni un (either ...)"), offset))
    return "object"


def _type_text(type_: str | tuple[str, ...]) -> str:
    return type_ if isinstance(type_, str) else "(either " + " ".join(type_) + ")"


def _head(node: SList) -> str:
    return node[0] if node and isinstance(node[0], str) else ""


def _signature(node: SExpr, issues: list[Issue], default_offset: int) -> Signature | None:
    if not isinstance(node, SList) or not node or not isinstance(node[0], str):
        issues.append(Issue("invalid-declaration", _("declaración no válida"), default_offset))
        return None
    parameters = typed_list(list(node[1:]), issues, node.offset)
    return Signature(node[0], tuple(parameters), None, node.offset)


def _define(text: str, kind: str) -> tuple[str, SList]:
    """Busca ``(define (<kind> nombre) ...)`` y devuelve el nombre y la S-expresión."""
    expressions = parse(text)
    for expression in expressions:
        if isinstance(expression, SList) and expression and expression[0] == "define":
            header = expression[1] if len(expression) > 1 else None
            if (
                not isinstance(header, SList)
                or len(header) != 2
                or header[0] != kind
                or not isinstance(header[1], str)
            ):
                raise PDDLStructureError(
                    _("se esperaba '(define ({kind} <nombre>) ...)'", kind=kind), expression.offset
                )
            return header[1], expression
    raise PDDLStructureError(_("no hay ningún '(define ({kind} ...))'", kind=kind))


def read_domain(text: str) -> Domain:
    """Lee un dominio a partir de su texto."""
    name, define = _define(text, "domain")
    domain = Domain(name, offset=define.offset)
    issues = domain.issues
    for section in define[2:]:
        if not isinstance(section, SList) or not section or not isinstance(section[0], str):
            issues.append(
                Issue("invalid-section", _("sección no válida"), offset_of(section, define.offset))
            )
            continue
        key = section[0]
        if key not in OPERATOR_KINDS and key != ":derived":
            if key in domain.section_offsets:
                issues.append(
                    Issue(
                        "repeated-section", _("sección '{key}' repetida", key=key), section.offset
                    )
                )
            domain.section_offsets[key] = section.offset
        body = list(section[1:])
        if key == ":requirements":
            domain.has_requirements = True
            domain.requirements.extend(r for r in body if isinstance(r, str))
        elif key == ":types":
            domain.has_types = True
            domain.types.extend(typed_list(body, issues, section.offset))
        elif key == ":constants":
            domain.constants.extend(typed_list(body, issues, section.offset))
        elif key == ":predicates":
            for item in body:
                signature = _signature(item, issues, section.offset)
                if signature:
                    domain.predicates.append(signature)
        elif key == ":functions":
            heads = {n.offset: n for n in body if isinstance(n, SList)}
            for typed in typed_list(body, issues, section.offset):
                head = heads.get(typed.offset)
                if head is None:
                    issues.append(
                        Issue(
                            "invalid-declaration",
                            _("función '{name}' declarada sin paréntesis", name=typed.name),
                            section.offset,
                        )
                    )
                    continue
                signature = _signature(head, issues, section.offset)
                if signature:
                    # Sin tipo, una función es numérica.
                    value_type = "number" if typed.type == "object" else typed.type
                    domain.functions.append(
                        Signature(
                            signature.name, signature.parameters, value_type, signature.offset
                        )
                    )
        elif key in OPERATOR_KINDS:
            domain.operators.append(_operator(OPERATOR_KINDS[key], section, issues))
        elif key == ":derived":
            if len(section) == 3 and isinstance(section[1], SList):
                domain.derived.append((section[1], section[2]))
            else:
                issues.append(
                    Issue("invalid-derived", _("regla ':derived' no válida"), section.offset)
                )
        elif key == ":constraints":
            domain.constraints = section[1] if len(section) > 1 else None
        else:
            issues.append(
                Issue("unknown-section", _("sección desconocida '{key}'", key=key), section.offset)
            )
    return domain


def _operator(kind: str, node: SList, issues: list[Issue]) -> Operator:
    name = node[1] if len(node) > 1 and isinstance(node[1], str) else ""
    if not name:
        issues.append(Issue("unnamed-operator", _("operador sin nombre"), node.offset))
    fields: dict[str, SExpr] = {}
    parameters: list[TypedName] = []
    i = 2
    while i < len(node):
        key = node[i]
        if not isinstance(key, str) or not key.startswith(":"):
            issues.append(
                Issue(
                    "invalid-field",
                    _("campo no válido en '{name}'", name=name),
                    offset_of(key, node.offset),
                )
            )
            i += 1
            continue
        value = node[i + 1] if i + 1 < len(node) else None
        if value is None or (isinstance(value, str) and value.startswith(":")):
            issues.append(
                Issue(
                    "missing-field-value",
                    _("campo '{key}' sin valor en '{name}'", key=key, name=name),
                    node.offset,
                )
            )
            i += 1
            continue
        if key == ":parameters":
            if isinstance(value, SList):
                parameters = typed_list(list(value), issues, value.offset)
            else:
                issues.append(
                    Issue(
                        "invalid-parameters",
                        _("parámetros no válidos en '{name}'", name=name),
                        node.offset,
                    )
                )
        else:
            fields[key] = value
        i += 2
    return Operator(kind, name, parameters, fields, node)


def read_problem(text: str) -> Problem:
    """Lee un problema a partir de su texto."""
    name, define = _define(text, "problem")
    problem = Problem(name, offset=define.offset)
    issues = problem.issues
    for section in define[2:]:
        if not isinstance(section, SList) or not section or not isinstance(section[0], str):
            issues.append(
                Issue("invalid-section", _("sección no válida"), offset_of(section, define.offset))
            )
            continue
        key = section[0]
        if key in problem.section_offsets:
            issues.append(
                Issue("repeated-section", _("sección '{key}' repetida", key=key), section.offset)
            )
        problem.section_offsets[key] = section.offset
        body = list(section[1:])
        if key == ":domain":
            if len(body) == 1 and isinstance(body[0], str):
                problem.domain_name = body[0]
                problem.domain_offset = section.offset
            else:
                issues.append(
                    Issue("invalid-domain", _("sección ':domain' no válida"), section.offset)
                )
        elif key == ":requirements":
            problem.requirements.extend(r for r in body if isinstance(r, str))
        elif key == ":objects":
            problem.objects.extend(typed_list(body, issues, section.offset))
        elif key == ":init":
            problem.init = body
        elif key == ":goal":
            problem.goal = body[0] if body else None
        elif key == ":constraints":
            problem.constraints = body[0] if body else None
        elif key == ":metric":
            if len(body) == 2 and body[0] in ("minimize", "maximize"):
                direction = body[0]
                assert isinstance(direction, str)
                problem.metric = (direction, body[1])
            else:
                issues.append(Issue("invalid-metric", _("métrica no válida"), section.offset))
        else:
            issues.append(
                Issue("unknown-section", _("sección desconocida '{key}'", key=key), section.offset)
            )
    return problem


def read_text(path: Path) -> str:
    """Lee un fichero PDDL como texto (UTF-8, tolerando bytes no válidos)."""
    return path.read_text(encoding="utf-8", errors="replace")
