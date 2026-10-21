"""Revisión de dominios y problemas: erratas, nombres sin declarar y rarezas de VAL.

Cada hallazgo tiene un nivel (``error``, ``warning`` o ``info``) y un código. Los errores son
lo que un planificador estricto rechazaría; los avisos, lo que es PDDL válido pero suele ser
una errata o da problemas con alguna herramienta; ``info``, lo que solo se muestra con
``--verbose``.

Los códigos son identificadores en inglés; los mensajes, en el idioma actual. Las
comprobaciones salen de las erratas encontradas al reunir el catálogo (ver
``docs/es/revision.md``):

* ``undeclared-requirement``: se usa una construcción sin declarar su requisito (las
  erratas marcadas con (*): ``total-cost`` sin ``:action-costs``, ``#t`` sin
  ``:continuous-effects``, la línea ``:requirements`` comentada…);
* ``glued-dash`` (``?t -tank``), ``malformed-variable`` (``? g``), ``type-without-names``
  (una línea ``- board`` sin objetos), ``function-without-parentheses`` (``(= d 0)``),
  ``repeated-value`` (dos valores iniciales para la misma función),
  ``uninitialized-function`` (una función que el dominio lee y el problema no inicializa);
* ``shared-name`` y ``repeated-declaration``: un nombre declarado dos veces (un tipo
  repetido, un dominio que se llama como un tipo…);
* nombres sin declarar (predicados, funciones, objetos, tipos, variables) y aridades.

Los códigos ``val-*`` avisan de lo que VAL no lleva bien (ver ``docs/es/val.md``): problemas
sin ``:init`` o funciones que se llaman como el dominio (fallo de segmentación),
``(:constraints (and))`` vacío, ``hold-after``, ``>`` estricto en restricciones y
``:object-fluents``.
"""

import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

from pddldomains.features import (
    KNOWN_REQUIREMENTS,
    REQUIREMENT_EXPANSIONS,
    domain_uses,
    problem_uses,
    undeclared,
    used_requirements,
)
from pddldomains.i18n import _
from pddldomains.pddl import (
    Domain,
    Issue,
    PDDLStructureError,
    Problem,
    Signature,
    TypedName,
    read_domain,
    read_problem,
    read_text,
)
from pddldomains.sexpr import LineIndex, PDDLSyntaxError, SExpr, SList, is_number, to_text

#: Niveles de los hallazgos, de más a menos grave.
LEVELS = ("error", "warning", "info")
#: Cómo se escribe cada nivel (se traduce al mostrarlo).
_LEVEL_LABELS = {"error": "error", "warning": "aviso", "info": "info"}

_COMPARISONS = frozenset({"<", ">", "<=", ">=", "="})
_ARITHMETIC = frozenset({"+", "-", "*", "/"})
_NUMERIC_EFFECTS = frozenset({"increase", "decrease", "assign", "scale-up", "scale-down"})
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
_COMMENT = re.compile(r";[^\n]*")
_LOOSE_QUESTION_MARK = re.compile(r"(?<![^\s(])\?(?=[\s()])")
#: Funciones que no hace falta declarar.
_BUILTIN_FUNCTIONS = frozenset({"total-time"})
#: Requisitos que no se cuentan como «declarados sin usar».
_NEVER_UNUSED = frozenset({":strips", ":adl", ":fluents", ":quantified-preconditions"})


@dataclass(frozen=True)
class Finding:
    """Un hallazgo de la revisión.

    Attributes:
        path: fichero.
        line: línea (0 si es del fichero entero).
        level: ``"error"``, ``"warning"`` o ``"info"``.
        code: identificador de la comprobación.
        message: descripción, en el idioma actual.
    """

    path: Path
    line: int
    level: str
    code: str
    message: str

    def format(self, base: Path | None = None) -> str:
        """``fichero:línea: nivel [código] mensaje``."""
        path = self.path
        if base is not None and path.is_relative_to(base):
            path = path.relative_to(base)
        location = f"{path}:{self.line}" if self.line else str(path)
        return f"{location}: {_(_LEVEL_LABELS[self.level])} [{self.code}] {self.message}"


#: Nivel de las anomalías que se encuentran al leer (:class:`pddldomains.pddl.Issue`).
_ISSUE_LEVELS = {"unknown-section": "warning"}


@dataclass
class _Report:
    path: Path
    lines: LineIndex
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, code: str, message: str, offset: int | None) -> None:
        line = self.lines.line(offset) if offset is not None else 0
        finding = Finding(self.path, line, level, code, message)
        if finding not in self.findings:
            self.findings.append(finding)


def _suggest(name: str, candidates: Iterable[str]) -> str:
    close = get_close_matches(name, sorted(candidates), n=1, cutoff=0.75)
    return _("; ¿quería decir '{name}'?", name=close[0]) if close else ""


class _TypeHierarchy:
    """Los tipos de un dominio y sus padres."""

    def __init__(self, domain: Domain) -> None:
        self.typed = domain.has_types
        self.parents: dict[str, set[str]] = {"object": set()}
        for typed in domain.types:
            parents = typed.type if isinstance(typed.type, tuple) else (typed.type,)
            self.parents.setdefault(typed.name, set()).update(p for p in parents if p != typed.name)
            # Un tipo que solo aparece como padre también cuenta como declarado (como en Fast
            # Downward): es habitual en los dominios de la IPC.
            for parent in parents:
                self.parents.setdefault(parent, set())

    def declared(self, name: str) -> bool:
        return name in self.parents or name == "number"

    def ancestors(self, name: str) -> set[str]:
        seen = {name}
        pending = [name]
        while pending:
            for parent in self.parents.get(pending.pop(), ()):
                if parent not in seen:
                    seen.add(parent)
                    pending.append(parent)
        seen.add("object")
        return seen

    def compatible(self, actual: str | tuple[str, ...], expected: str | tuple[str, ...]) -> bool:
        actuals = actual if isinstance(actual, tuple) else (actual,)
        expecteds = set(expected if isinstance(expected, tuple) else (expected,))
        return all(self.ancestors(a) & expecteds for a in actuals)


class _Checker:
    """Comprueba fórmulas, efectos y expresiones contra las declaraciones de un dominio."""

    def __init__(self, domain: Domain, report: _Report, names: dict[str, TypedName]) -> None:
        self.domain = domain
        self.report = report
        self.types = _TypeHierarchy(domain)
        self.names = names  # constantes (y objetos, en un problema) con su tipo
        self.predicates: dict[str, Signature] = {p.name: p for p in domain.predicates}
        for head, _body in domain.derived:
            if head and isinstance(head[0], str) and head[0] not in self.predicates:
                self.predicates[head[0]] = Signature(
                    head[0], tuple(_variables(head[1:])), None, head.offset
                )
        self.functions: dict[str, Signature] = {f.name: f for f in domain.functions}
        self.preferences: set[str] = set()
        self.preference_uses: list[tuple[str, int]] = []
        #: Comparaciones estrictas en restricciones (VAL las evalúa como no estrictas).
        self.strict_comparisons: list[int] = []
        #: Funciones que se leen y funciones a las que se da valor con ``assign``, para
        #: ``funcion-sin-valor``.
        self.read_functions: dict[str, int] = {}
        self.assigned_functions: set[str] = set()
        self.ground = False  # en un problema, los átomos de :init tienen que ser cerrados

    def error(self, code: str, message: str, offset: int | None) -> None:
        self.report.add("error", code, message, offset)

    def warn(self, code: str, message: str, offset: int | None) -> None:
        self.report.add("warning", code, message, offset)

    # --- Términos ------------------------------------------------------------------------

    def term(
        self, term: SExpr, scope: dict[str, str | tuple[str, ...]], offset: int
    ) -> str | tuple[str, ...] | None:
        """Comprueba un término y devuelve su tipo, si se conoce."""
        if isinstance(term, SList):
            return self.function_term(term, scope, offset, numeric=False)
        if term == "?":
            self.error(
                "malformed-variable", _("'?' suelto: ¿un espacio tras la interrogación?"), offset
            )
            return None
        if term.startswith("?"):
            if term not in scope:
                self.error(
                    "unbound-variable", _("variable '{name}' sin declarar", name=term), offset
                )
                return None
            return scope[term]
        if is_number(term):
            self.error(
                "invalid-term", _("número '{value}' como argumento de un átomo", value=term), offset
            )
            return None
        if term not in self.names:
            self.error(
                "undeclared-object",
                _(
                    "objeto o constante '{name}' sin declarar{hint}",
                    name=term,
                    hint=_suggest(term, self.names),
                ),
                offset,
            )
            return None
        return self.names[term].type

    def arguments(
        self,
        node: SList,
        signature: Signature,
        scope: dict[str, str | tuple[str, ...]],
        offset: int,
        what: str,
    ) -> None:
        arguments = node[1:]
        if len(arguments) != len(signature.parameters):
            self.error(
                "arity",
                _(
                    "{what} '{name}' con {count} argumentos (se declaró con {declared})",
                    what=what,
                    name=signature.name,
                    count=len(arguments),
                    declared=len(signature.parameters),
                ),
                offset,
            )
        for argument, parameter in zip(arguments, signature.parameters, strict=False):
            actual = self.term(argument, scope, offset)
            if (
                self.ground
                and self.types.typed
                and actual is not None
                and not self.types.compatible(actual, parameter.type)
            ):
                self.warn(
                    "incompatible-type",
                    _(
                        "'{argument}' ({type}) en {atom}: el parámetro es de tipo {expected}",
                        argument=to_text(argument),
                        type=_type_text(actual),
                        atom=to_text(node, 50),
                        expected=_type_text(parameter.type),
                    ),
                    offset,
                )

    def atom(self, node: SList, scope: dict[str, str | tuple[str, ...]], offset: int) -> None:
        head = node[0]
        if not isinstance(head, str):
            self.error(
                "invalid-formula", _("fórmula no válida: {node}", node=to_text(node)), offset
            )
            return
        if head == "=" and len(node) == 3:
            for argument in node[1:]:
                self.term(argument, scope, offset)
            return
        signature = self.predicates.get(head)
        if signature is None:
            if head in self.functions:
                self.error(
                    "function-as-predicate",
                    _("'{name}' es una función, no un predicado", name=head),
                    offset,
                )
            else:
                self.error(
                    "undeclared-predicate",
                    _(
                        "predicado '{name}' sin declarar{hint}",
                        name=head,
                        hint=_suggest(head, self.predicates),
                    ),
                    offset,
                )
            for argument in node[1:]:
                self.term(argument, scope, offset)
            return
        self.arguments(node, signature, scope, offset, _("predicado"))

    def function_term(
        self,
        node: SList,
        scope: dict[str, str | tuple[str, ...]],
        offset: int,
        *,
        numeric: bool = True,
        read: bool = True,
    ) -> str | tuple[str, ...] | None:
        head = node[0] if node else None
        if not isinstance(head, str):
            self.error(
                "invalid-expression", _("expresión no válida: {node}", node=to_text(node)), offset
            )
            return None
        if head in _BUILTIN_FUNCTIONS and len(node) == 1:
            return "number"
        signature = self.functions.get(head)
        if signature is None:
            if head in self.predicates:
                self.error(
                    "predicate-as-function",
                    _("'{name}' es un predicado, no una función", name=head),
                    offset,
                )
            else:
                self.error(
                    "undeclared-function",
                    _(
                        "función '{name}' sin declarar{hint}",
                        name=head,
                        hint=_suggest(head, self.functions),
                    ),
                    offset,
                )
            return None
        if read:
            self.read_functions.setdefault(head, offset)
        self.arguments(node, signature, scope, offset, _("función"))
        return signature.type

    # --- Fórmulas ------------------------------------------------------------------------

    def formula(
        self,
        node: SExpr,
        scope: dict[str, str | tuple[str, ...]],
        offset: int,
        *,
        constraint: bool = False,
    ) -> None:
        if isinstance(node, str):
            self.error(
                "invalid-formula", _("se esperaba una fórmula y hay '{node}'", node=node), offset
            )
            return
        if not node:
            return
        offset = node.offset
        head = node[0]
        args = node[1:]
        if head == "and":
            for arg in args:
                self.formula(arg, scope, offset, constraint=constraint)
        elif head in ("or", "imply", "not"):
            if (head == "not" and len(args) != 1) or (head == "imply" and len(args) != 2):
                self.error(
                    "invalid-formula",
                    _("'{head}' con {count} argumentos", head=head, count=len(args)),
                    offset,
                )
            for arg in args:
                self.formula(arg, scope, offset, constraint=constraint)
        elif head in ("exists", "forall"):
            if len(node) != 3 or not isinstance(node[1], SList):
                self.error("invalid-formula", _("'{head}' mal formado", head=head), offset)
                return
            inner = {**scope, **self.variables(node[1], offset)}
            self.formula(node[2], inner, offset, constraint=constraint)
        elif head == "preference":
            if len(args) == 2 and isinstance(args[0], str):
                self.preferences.add(args[0])
            if args:
                self.formula(args[-1], scope, offset, constraint=constraint)
        elif _is_timed(node):
            self.formula(node[2], scope, offset, constraint=constraint)
        elif constraint and head in _MODAL:
            times = _MODAL[head]
            if head == "hold-after":
                self.warn(
                    "val-hold-after",
                    _("VAL no evalúa bien 'hold-after' (ver docs/es/val.md)"),
                    offset,
                )
            for time in args[:times]:
                self.expression(time, scope, offset)
            for arg in args[times:]:
                self.formula(arg, scope, offset, constraint=True)
        elif head in _COMPARISONS and len(node) == 3:
            if head in (">", "<") and constraint:
                self.strict_comparisons.append(offset)
            if head == "=" and not any(self.numeric(a) for a in args):
                for arg in args:
                    self.term(arg, scope, offset)
            else:
                for arg in args:
                    self.expression(arg, scope, offset)
        else:
            self.atom(node, scope, offset)

    def numeric(self, term: SExpr) -> bool:
        if isinstance(term, SList):
            head = term[0] if term else None
            signature = self.functions.get(head) if isinstance(head, str) else None
            return signature is None or signature.type == "number"
        return is_number(term) or (term in self.functions and term not in self.names)

    def variables(self, node: SList, offset: int) -> dict[str, str | tuple[str, ...]]:
        from pddldomains.pddl import typed_list

        issues: list[Issue] = []
        variables = typed_list(list(node), issues, offset)
        for issue in issues:
            self.error(issue.code, issue.message, issue.offset)
        result: dict[str, str | tuple[str, ...]] = {}
        for variable in variables:
            if not variable.name.startswith("?"):
                self.error(
                    "malformed-variable",
                    _("'{name}' no es una variable", name=variable.name),
                    offset,
                )
            self.check_type(variable.type, offset)
            result[variable.name] = variable.type
        return result

    def check_type(self, type_: str | tuple[str, ...], offset: int) -> None:
        for name in type_ if isinstance(type_, tuple) else (type_,):
            if not self.types.declared(name):
                self.error(
                    "undeclared-type",
                    _(
                        "tipo '{name}' sin declarar{hint}",
                        name=name,
                        hint=_suggest(name, self.types.parents),
                    ),
                    offset,
                )

    # --- Efectos y expresiones -------------------------------------------------------------

    def effect(self, node: SExpr, scope: dict[str, str | tuple[str, ...]], offset: int) -> None:
        if isinstance(node, str):
            self.error(
                "invalid-effect", _("se esperaba un efecto y hay '{node}'", node=node), offset
            )
            return
        if not node:
            return
        offset = node.offset
        head = node[0]
        if head == "and":
            for arg in node[1:]:
                self.effect(arg, scope, offset)
        elif head == "not" and len(node) == 2 and isinstance(node[1], SList):
            self.atom(node[1], scope, offset)
        elif head == "forall" and len(node) == 3 and isinstance(node[1], SList):
            self.effect(node[2], {**scope, **self.variables(node[1], offset)}, offset)
        elif head == "when" and len(node) == 3:
            self.formula(node[1], scope, offset)
            self.effect(node[2], scope, offset)
        elif _is_timed(node):
            self.effect(node[2], scope, offset)
        elif head in _NUMERIC_EFFECTS and len(node) == 3:
            target = node[1]
            if isinstance(target, SList):
                self.function_term(target, scope, offset, read=head != "assign")
                if head == "assign" and target and isinstance(target[0], str):
                    self.assigned_functions.add(target[0])
            else:
                self.bare_function(target, offset)
            self.expression(node[2], scope, offset)
        else:
            self.atom(node, scope, offset)

    def bare_function(self, name: str, offset: int) -> None:
        if name in self.functions:
            self.error(
                "function-without-parentheses",
                _("función '{name}' sin paréntesis: '({name})'", name=name),
                offset,
            )
        else:
            self.error("invalid-expression", _("'{name}' no es una función", name=name), offset)

    def expression(self, node: SExpr, scope: dict[str, str | tuple[str, ...]], offset: int) -> None:
        if isinstance(node, str):
            if is_number(node) or node in ("#t", "?duration", "total-time"):
                return
            if node.startswith("?"):
                self.term(node, scope, offset)
            elif node in self.functions:
                self.bare_function(node, offset)
            elif node not in self.names:
                self.error(
                    "invalid-expression",
                    _("'{name}' no es un número ni una función", name=node),
                    offset,
                )
            return
        if not node:
            return
        head = node[0]
        if head in _ARITHMETIC:
            for arg in node[1:]:
                self.expression(arg, scope, node.offset)
        elif head == "is-violated":
            if len(node) == 2 and isinstance(node[1], str):
                self.preference_uses.append((node[1], node.offset))
        else:
            self.function_term(node, scope, node.offset)


def _variables(items: Iterable[SExpr]) -> list[TypedName]:
    from pddldomains.pddl import typed_list

    return typed_list(list(items), [], 0)


def _is_timed(node: SList) -> bool:
    return (
        len(node) == 3
        and isinstance(node[2], SList)
        and (
            (node[0] == "at" and node[1] in ("start", "end"))
            or (node[0] == "over" and node[1] == "all")
        )
    )


def _type_text(type_: str | tuple[str, ...]) -> str:
    return type_ if isinstance(type_, str) else "(either " + " ".join(type_) + ")"


def _issues(report: _Report, issues: Iterable[Issue]) -> None:
    for issue in issues:
        report.add(_ISSUE_LEVELS.get(issue.code, "error"), issue.code, issue.message, issue.offset)


def _duplicates(report: _Report, kind: str, names: Iterable[tuple[str, int]]) -> None:
    seen: dict[str, int] = {}
    for name, offset in names:
        if name in seen:
            report.add(
                "error",
                "repeated-declaration",
                _("'{name}' declarado dos veces como {kind}", name=name, kind=kind),
                offset,
            )
        else:
            seen[name] = offset


def _shared_names(report: _Report, namespaces: Mapping[str, Iterable[tuple[str, int]]]) -> None:
    """Avisa de los nombres que aparecen en dos espacios de nombres distintos."""
    owner: dict[str, str] = {}
    for kind, names in namespaces.items():
        for name, offset in names:
            previous = owner.get(name)
            if previous is None:
                owner[name] = kind
            elif previous != kind:
                report.add(
                    "warning",
                    "shared-name",
                    _(
                        "'{name}' es a la vez {previous} y {kind}",
                        name=name,
                        previous=previous,
                        kind=kind,
                    ),
                    offset,
                )


def lint_domain(path: Path, text: str | None = None) -> tuple[Domain | None, list[Finding]]:
    """Revisa un dominio. Devuelve el dominio leído (``None`` si no se pudo) y los hallazgos."""
    text = read_text(path) if text is None else text
    report = _Report(path, LineIndex(text))
    try:
        domain = read_domain(text)
    except (PDDLSyntaxError, PDDLStructureError) as error:
        report.add("error", "syntax", str(error), error.offset)
        return None, report.findings
    _issues(report, domain.issues)
    _check_tokens(report, text)
    for requirement in domain.requirements:
        if requirement not in KNOWN_REQUIREMENTS:
            close = _suggest(requirement, KNOWN_REQUIREMENTS)
            report.add(
                "error",
                "unknown-requirement",
                _("requisito desconocido '{name}'{hint}", name=requirement, hint=close),
                domain.section_offsets.get(":requirements"),
            )
    uses = domain_uses(domain)
    for use in undeclared(uses, domain.requirements):
        report.add(
            "error",
            "undeclared-requirement",
            _(
                "falta declarar '{requirement}' (lo necesita {construct})",
                requirement=use.requirement,
                construct=use.construct,
            ),
            use.offset,
        )
    _unused_requirements(report, domain, used_requirements(uses))
    _duplicates(report, _("tipo"), ((t.name, t.offset) for t in domain.types))
    _duplicates(report, _("constante"), ((c.name, c.offset) for c in domain.constants))
    _duplicates(report, _("predicado"), ((p.name, p.offset) for p in domain.predicates))
    _duplicates(report, _("función"), ((f.name, f.offset) for f in domain.functions))
    _duplicates(report, _("operador"), ((o.name, o.node.offset) for o in domain.operators))
    _shared_names(report, _domain_namespaces(domain))
    for function in domain.functions:
        if function.name == domain.name:
            report.add(
                "warning",
                "val-function-named-like-domain",
                _(
                    "la función '{name}' se llama como el dominio: VAL falla (segfault)",
                    name=function.name,
                ),
                function.offset,
            )
        if function.type != "number":
            report.add(
                "warning",
                "val-object-fluents",
                _(
                    "función de objetos '{name}': VAL falla con :object-fluents (segfault)",
                    name=function.name,
                ),
                function.offset,
            )
    names = {c.name: c for c in domain.constants}
    checker = _Checker(domain, report, names)
    for constant in domain.constants:
        checker.check_type(constant.type, constant.offset)
    for signature in (*domain.predicates, *domain.functions):
        for parameter in signature.parameters:
            if not parameter.name.startswith("?"):
                report.add(
                    "error",
                    "malformed-variable",
                    _(
                        "parámetro '{name}' de '{owner}' sin '?'",
                        name=parameter.name,
                        owner=signature.name,
                    ),
                    signature.offset,
                )
            checker.check_type(parameter.type, signature.offset)
        if signature.type not in (None, "number"):
            checker.check_type(signature.type, signature.offset)
    for operator in domain.operators:
        offset = operator.node.offset
        scope: dict[str, str | tuple[str, ...]] = {}
        for parameter in operator.parameters:
            if not parameter.name.startswith("?"):
                report.add(
                    "error",
                    "malformed-variable",
                    _(
                        "parámetro '{name}' de '{owner}' sin '?'",
                        name=parameter.name,
                        owner=operator.name,
                    ),
                    offset,
                )
            checker.check_type(parameter.type, offset)
            scope[parameter.name] = parameter.type
        _duplicates(
            report,
            _("parámetro de '{name}'", name=operator.name),
            ((p.name, offset) for p in operator.parameters),
        )
        if operator.kind == "durative-action":
            scope["?duration"] = "number"
            for key in (":duration", ":condition", ":effect"):
                if key not in operator.fields:
                    report.add(
                        "error",
                        "missing-field-value",
                        _("'{name}' sin '{key}'", name=operator.name, key=key),
                        offset,
                    )
            if ":duration" in operator.fields:
                checker.formula(operator.fields[":duration"], scope, offset)
            if ":condition" in operator.fields:
                checker.formula(operator.fields[":condition"], scope, offset)
        elif ":precondition" in operator.fields:
            checker.formula(operator.fields[":precondition"], scope, offset)
        if ":effect" in operator.fields:
            checker.effect(operator.fields[":effect"], scope, offset)
        elif operator.kind != "durative-action":
            report.add(
                "warning",
                "missing-effect",
                _("'{name}' no tiene ':effect'", name=operator.name),
                offset,
            )
    for head, body in domain.derived:
        variables = {v.name: v.type for v in _variables(head[1:])}
        checker.formula(body, variables, head.offset)
    if domain.constraints is not None:
        checker.formula(
            domain.constraints, {}, domain.section_offsets.get(":constraints", 0), constraint=True
        )
    return domain, report.findings


def _unused_requirements(report: _Report, domain: Domain, used: frozenset[str]) -> None:
    used_expanded = set(used)
    if ":action-costs" in used:
        used_expanded.add(":numeric-fluents")
    for requirement in domain.requirements:
        if requirement in _NEVER_UNUSED or requirement not in KNOWN_REQUIREMENTS:
            continue
        implied = REQUIREMENT_EXPANSIONS.get(requirement, frozenset({requirement}))
        if not implied & used_expanded:
            report.add(
                "info",
                "unused-requirement",
                _("'{requirement}' declarado pero no usado", requirement=requirement),
                domain.section_offsets.get(":requirements"),
            )


def _domain_namespaces(domain: Domain) -> dict[str, list[tuple[str, int]]]:
    return {
        _("el dominio"): [(domain.name, domain.offset)],
        _("un tipo"): [(t.name, t.offset) for t in domain.types if t.name != "object"],
        _("una constante"): [(c.name, c.offset) for c in domain.constants],
        _("un predicado"): [(p.name, p.offset) for p in domain.predicates],
        _("una función"): [(f.name, f.offset) for f in domain.functions],
        _("un operador"): [(o.name, o.node.offset) for o in domain.operators],
    }


def _check_tokens(report: _Report, text: str) -> None:
    """Comprobaciones sobre el texto: interrogaciones sueltas (``? g``)."""
    code = _COMMENT.sub(lambda m: " " * len(m.group()), text)
    for match in _LOOSE_QUESTION_MARK.finditer(code):
        report.add(
            "error",
            "malformed-variable",
            _("'?' suelto: ¿un espacio tras la interrogación?"),
            match.start(),
        )


def lint_problem(path: Path, domain: Domain, text: str | None = None) -> list[Finding]:
    """Revisa un problema con su dominio (ya leído)."""
    text = read_text(path) if text is None else text
    report = _Report(path, LineIndex(text))
    try:
        problem = read_problem(text)
    except (PDDLSyntaxError, PDDLStructureError) as error:
        report.add("error", "syntax", str(error), error.offset)
        return report.findings
    _issues(report, problem.issues)
    _check_tokens(report, text)
    if problem.domain_name and problem.domain_name != domain.name:
        report.add(
            "error",
            "domain-mismatch",
            _(
                "el problema es del dominio '{expected}' y el dominio se llama '{name}'",
                expected=problem.domain_name,
                name=domain.name,
            ),
            problem.domain_offset,
        )
    uses = [*domain_uses(domain), *problem_uses(problem, domain)]
    domain_missing = {u.requirement for u in undeclared(domain_uses(domain), domain.requirements)}
    for use in undeclared(uses, [*domain.requirements, *problem.requirements]):
        if use.requirement not in domain_missing:  # los del dominio ya se cuentan en el dominio
            report.add(
                "error",
                "undeclared-requirement",
                _(
                    "falta declarar '{requirement}' en el dominio (lo necesita {construct})",
                    requirement=use.requirement,
                    construct=use.construct,
                ),
                use.offset,
            )
    _duplicates(report, _("objeto"), ((o.name, o.offset) for o in problem.objects))
    namespaces: dict[str, list[tuple[str, int]]] = {
        **_domain_namespaces(domain),
        _("un objeto"): [(o.name, o.offset) for o in problem.objects],
        _("el problema"): [(problem.name, problem.offset)],
    }
    # Los nombres compartidos dentro del dominio ya se cuentan al revisar el dominio.
    _problem_shared_names(report, namespaces)
    names = {c.name: c for c in domain.constants}
    names.update({o.name: o for o in problem.objects})
    checker = _Checker(domain, report, names)
    for typed in problem.objects:
        checker.check_type(typed.type, typed.offset)
    if problem.init is None:
        report.add(
            "warning",
            "val-missing-init",
            _("el problema no tiene ':init': VAL falla (segfault)"),
            problem.offset,
        )
    initialized = _check_init(report, checker, problem)
    if problem.goal is None:
        report.add("error", "missing-goal", _("el problema no tiene ':goal'"), problem.offset)
    else:
        checker.formula(problem.goal, {}, problem.section_offsets.get(":goal", problem.offset))
    if problem.constraints is not None:
        offset = problem.section_offsets.get(":constraints", problem.offset)
        if isinstance(problem.constraints, SList) and problem.constraints == ["and"]:
            report.add(
                "warning",
                "val-empty-constraints",
                _(
                    "'(:constraints (and))' vacío: VAL da mal el valor de las preferencias del "
                    "objetivo"
                ),
                offset,
            )
        checker.formula(problem.constraints, {}, offset, constraint=True)
    for operator in domain.operators:  # preferencias en las precondiciones
        for key in (":precondition", ":condition"):
            if key in operator.fields:
                _collect_preferences(operator.fields[key], checker.preferences)
    if problem.metric is not None:
        checker.expression(
            problem.metric[1], {}, problem.section_offsets.get(":metric", problem.offset)
        )
    if checker.strict_comparisons:
        count = len(checker.strict_comparisons)
        report.add(
            "warning",
            "val-strict-comparison",
            _(
                "{count} comparaciones estrictas ('>' o '<') en restricciones: VAL las evalúa "
                "como '>=' o '<='",
                count=count,
            ),
            checker.strict_comparisons[0],
        )
    for name, offset in checker.preference_uses:
        if name not in checker.preferences:
            report.add(
                "error",
                "undeclared-preference",
                _("'is-violated {name}': no hay ninguna preferencia '{name}'", name=name),
                offset,
            )
    _check_uninitialized(report, domain, problem, initialized)
    return report.findings


def _problem_shared_names(report: _Report, namespaces: dict[str, list[tuple[str, int]]]) -> None:
    problem_kinds = {_("un objeto"), _("el problema")}
    owner: dict[str, str] = {}
    for kind, names in namespaces.items():
        for name, offset in names:
            previous = owner.get(name)
            if previous is None:
                owner[name] = kind
            elif previous != kind and (kind in problem_kinds or previous in problem_kinds):
                report.add(
                    "warning",
                    "shared-name",
                    _(
                        "'{name}' es a la vez {previous} y {kind}",
                        name=name,
                        previous=previous,
                        kind=kind,
                    ),
                    offset,
                )


def _collect_preferences(node: SExpr, names: set[str]) -> None:
    if isinstance(node, SList):
        if node and node[0] == "preference" and len(node) == 3 and isinstance(node[1], str):
            names.add(node[1])
        for child in node:
            _collect_preferences(child, names)


def _check_init(report: _Report, checker: _Checker, problem: Problem) -> set[str]:
    """Revisa ``:init`` y devuelve las funciones que reciben valor inicial."""
    checker.ground = True
    initialized: set[str] = set()
    values: Counter[str] = Counter()
    facts: Counter[str] = Counter()
    offset = problem.section_offsets.get(":init", problem.offset)
    for fact in problem.init or ():
        if not isinstance(fact, SList) or not fact:
            report.add(
                "error",
                "invalid-fact",
                _("hecho no válido en ':init': '{fact}'", fact=to_text(fact)),
                offset,
            )
            continue
        head = fact[0]
        if head == "=" and len(fact) == 3:
            target, value = fact[1], fact[2]
            if isinstance(target, str):
                checker.bare_function(target, fact.offset)
                initialized.add(target)
                key = f"({target})"
            else:
                checker.function_term(target, {}, fact.offset, read=False)
                if target and isinstance(target[0], str):
                    initialized.add(target[0])
                key = to_text(target, 0)
            values[key] += 1
            if values[key] == 2:
                report.add(
                    "error",
                    "repeated-value",
                    _("{key} recibe dos valores iniciales (VAL se queda con el último)", key=key),
                    fact.offset,
                )
            if isinstance(value, SList) or (not is_number(value) and value not in checker.names):
                report.add(
                    "error",
                    "invalid-value",
                    _("valor inicial no válido: {fact}", fact=to_text(fact)),
                    fact.offset,
                )
            continue
        literal = fact[2] if head == "at" and len(fact) == 3 and is_number(fact[1]) else fact
        if isinstance(literal, SList) and literal and literal[0] == "not" and len(literal) == 2:
            literal = literal[1]
        if not isinstance(literal, SList):
            report.add(
                "error",
                "invalid-fact",
                _("hecho no válido en ':init': '{fact}'", fact=to_text(fact)),
                fact.offset,
            )
            continue
        key = to_text(fact, 0)
        facts[key] += 1
        if facts[key] == 2:
            report.add(
                "warning",
                "repeated-fact",
                _("hecho repetido en ':init': {fact}", fact=key),
                fact.offset,
            )
        checker.atom(literal, {}, fact.offset)
    checker.ground = False
    return initialized


def _check_uninitialized(
    report: _Report, domain: Domain, problem: Problem, initialized: set[str]
) -> None:
    """Avisa de las funciones que el dominio lee y el problema no inicializa en absoluto."""
    reader = _Checker(
        domain, _Report(report.path, report.lines), {c.name: c for c in domain.constants}
    )
    static = _static_predicates(domain)
    present = {
        _fact_predicate(fact) for fact in problem.init or () if _fact_predicate(fact) is not None
    }
    for operator in domain.operators:
        condition = operator.fields.get(":precondition", operator.fields.get(":condition"))
        if any(atom in static and atom not in present for atom in _required_atoms(condition)):
            continue  # nunca aplicable en este problema: sus funciones no hacen falta
        scope: dict[str, str | tuple[str, ...]] = {p.name: p.type for p in operator.parameters}
        scope["?duration"] = "number"
        for key, value in operator.fields.items():
            if key == ":effect":
                reader.effect(value, scope, 0)
            else:
                reader.formula(value, scope, 0)
    for head, body in domain.derived:
        reader.formula(body, {v.name: v.type for v in _variables(head[1:])}, 0)
    # Una función a la que el dominio da valor con assign puede no necesitar valor inicial
    # (generator-toricelli las asigna al empezar la acción que las lee).
    missing = sorted(set(reader.read_functions) - initialized - reader.assigned_functions)
    for name in missing:
        report.add(
            "warning",
            "uninitialized-function",
            _(
                "el dominio usa la función '{name}' y el problema no le da ningún valor inicial",
                name=name,
            ),
            problem.section_offsets.get(":init", problem.offset),
        )


def _static_predicates(domain: Domain) -> set[str]:
    """Predicados que ningún efecto cambia."""
    changed: set[str] = set()

    def walk(node: SExpr) -> None:
        if not isinstance(node, SList) or not node:
            return
        head = node[0]
        if head in ("and", "forall", "when", "at", "not") or head in _NUMERIC_EFFECTS:
            for child in node[1:]:
                walk(child)
        elif isinstance(head, str):
            changed.add(head)

    for operator in domain.operators:
        walk(operator.fields.get(":effect", SList(0)))
    derived = {head[0] for head, _body in domain.derived if head and isinstance(head[0], str)}
    return {p.name for p in domain.predicates} - changed - derived


def _required_atoms(node: SExpr | None) -> Iterator[str]:
    """Predicados de los átomos positivos de una conjunción (y de sus ``at start``…)."""
    if not isinstance(node, SList) or not node:
        return
    if node[0] == "and":
        for child in node[1:]:
            yield from _required_atoms(child)
    elif _is_timed(node):
        yield from _required_atoms(node[2])
    elif (
        isinstance(node[0], str)
        and node[0] not in _COMPARISONS
        and node[0]
        not in (
            "or",
            "not",
            "imply",
            "exists",
            "forall",
            "preference",
        )
    ):
        yield node[0]


def _fact_predicate(fact: SExpr) -> str | None:
    if not isinstance(fact, SList) or not fact:
        return None
    if fact[0] == "at" and len(fact) == 3 and is_number(fact[1]):
        fact = fact[2]
    if not isinstance(fact, SList) or not fact or fact[0] in ("=", "not"):
        return None
    head = fact[0]
    return head if isinstance(head, str) else None


def summarize(findings: Iterable[Finding]) -> dict[str, int]:
    """Número de hallazgos por nivel."""
    counts = Counter(f.level for f in findings)
    return {level: counts.get(level, 0) for level in LEVELS}
