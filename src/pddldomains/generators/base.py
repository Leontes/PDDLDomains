"""Base de los generadores de problemas.

Un generador produce problemas para el dominio de una colección del catálogo. Sus
parámetros (:class:`Param`) admiten tres formas de valor en la línea de comandos:

* un valor: ``-p tanks=4``;
* un rango aleatorio: ``-p tanks=2..8`` (entero o real según el parámetro), que se sortea
  para cada problema con su semilla;
* una serie: ``-p tanks=2,4,6``, que genera los problemas pedidos para cada valor (con
  varias series, para cada combinación).

Cada problema se genera con su propia semilla, así que una generación se repite exactamente
con la misma semilla inicial y los mismos parámetros.
"""

import inspect
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pddldomains.catalog import Catalog, Collection
from pddldomains.i18n import _


class GeneratorError(Exception):
    """Parámetros no válidos o un generador que no se puede ejecutar."""


@dataclass(frozen=True)
class Param:
    """Un parámetro de un generador.

    Attributes:
        name: nombre (con guiones: ``max-int``).
        kind: ``int``, ``float`` o ``str``.
        default: valor por defecto (admite rangos ``"a..b"``); ``None`` si es obligatorio.
        help: descripción.
        choices: valores admitidos (para ``str``).
        minimum: valor mínimo (para números).
        per_item: si el generador recibe el valor sin resolver y sortea un rango cada vez que
            lo usa (por ejemplo, para cada depósito) en lugar de una vez por problema.
    """

    name: str
    kind: type
    default: Any
    help: str
    choices: tuple[str, ...] | None = None
    minimum: float | None = None
    per_item: bool = False

    def resolve(self, value: Any, rng: random.Random) -> Any:
        """Convierte un valor (o sortea un rango ``a..b``) y lo comprueba."""
        if isinstance(value, str) and ".." in value and self.kind in (int, float):
            low_text, high_text = value.split("..", 1)
            low, high = self.convert(low_text), self.convert(high_text)
            if low > high:
                raise GeneratorError(
                    _("{name}: rango vacío '{value}'", name=self.name, value=value)
                )
            value = rng.randint(low, high) if self.kind is int else round(rng.uniform(low, high), 3)
        else:
            value = self.convert(value)
        if self.minimum is not None and value < self.minimum:
            raise GeneratorError(
                _(
                    "{name} tiene que ser al menos {minimum:g} (es {value})",
                    name=self.name,
                    minimum=self.minimum,
                    value=value,
                )
            )
        if self.choices is not None and value not in self.choices:
            raise GeneratorError(
                _(
                    "{name} tiene que ser uno de {choices} (es '{value}')",
                    name=self.name,
                    choices=list(self.choices),
                    value=value,
                )
            )
        return value

    def convert(self, value: Any) -> Any:
        try:
            return self.kind(value)
        except (TypeError, ValueError) as error:
            raise GeneratorError(
                _(
                    "{name}: '{value}' no es un {kind}",
                    name=self.name,
                    value=value,
                    kind=self.kind.__name__,
                )
            ) from error


@dataclass
class GeneratedProblem:
    """Un problema generado.

    Attributes:
        problem: texto PDDL del problema.
        plan: un plan válido, si el generador lo conoce.
        notes: comentarios para el manifiesto (parámetros derivados…).
        domain: el fichero de dominio del catálogo que usa, si no es el común de la colección
            (en las colecciones con un dominio por problema).
    """

    problem: str
    plan: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)
    domain: Path | None = None


class Generator(ABC):
    """Un generador de problemas para el dominio de una colección.

    Attributes:
        name: nombre con el que se elige en la línea de comandos.
        collection: identificador de la colección cuyo dominio usa.
        description: qué genera, en una línea.
        origin: de dónde sale (``"own"``, propio; ``"ported"``, portado; ``"pddl-generators"``
            o ``"IPC 2023"``).
        params: sus parámetros.
    """

    name: str
    collection: str
    description: str
    origin: str = "own"
    params: tuple[Param, ...] = ()

    def unavailable(self) -> str | None:
        """Por qué no se puede usar ahora (falta compilar algo…), o ``None``."""
        return None

    def collection_of(self, catalog: Catalog, params: dict[str, Any]) -> Collection:
        """La colección cuyo dominio usan los problemas generados."""
        return catalog.find(self.collection)

    @abstractmethod
    def generate(
        self, params: dict[str, Any], seed: int, name: str, collection: Collection
    ) -> GeneratedProblem:
        """Genera un problema llamado ``name`` con parámetros ya resueltos."""

    def param(self, name: str) -> Param:
        """El parámetro ``name``."""
        for param in self.params:
            if param.name == name:
                return param
        known = ", ".join(p.name for p in self.params) or _("ninguno")
        raise GeneratorError(
            _(
                "'{generator}' no tiene el parámetro '{name}' (tiene: {known})",
                generator=self.name,
                name=name,
                known=known,
            )
        )

    def explanation(self) -> str:
        """Cómo genera y por qué sus problemas tienen solución (lo que muestra ``--params``).

        Es el docstring de la clase, en español; se traduce al mostrarlo.
        """
        return inspect.getdoc(type(self)) or ""

    def check(self, params: dict[str, Any]) -> None:  # noqa: B027 (opcional, no abstracto)
        """Comprobaciones entre parámetros ya resueltos (lanza :class:`GeneratorError`)."""


# --- Ayudas para escribir y retocar PDDL -------------------------------------------------


def _token(name: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w\-?]){re.escape(name)}(?![\w\-])", re.IGNORECASE)


def rename_tokens(text: str, mapping: dict[str, str]) -> str:
    """Renombra símbolos (predicados, objetos…) respetando los límites de los nombres PDDL."""
    for old, new in mapping.items():
        text = _token(old).sub(new, text)
    return text


def set_problem_name(text: str, name: str) -> str:
    """Cambia el nombre del problema (``(problem X)``)."""
    return re.sub(
        r"\(\s*problem\s+[^\s()]+\s*\)", f"(problem {name})", text, count=1, flags=re.IGNORECASE
    )


def set_domain_name(text: str, name: str) -> str:
    """Cambia el dominio del problema (``(:domain X)``)."""
    return re.sub(
        r"\(\s*:domain\s+[^\s()]+\s*\)", f"(:domain {name})", text, count=1, flags=re.IGNORECASE
    )


def ensure_total_cost(text: str) -> str:
    """Añade ``(= (total-cost) 0)`` a ``:init`` y la métrica de coste si faltan.

    Algunos generadores de pddl-generators no los escriben, aunque los problemas de la IPC
    sí: sin valor inicial, ``total-cost`` queda indefinido (VAL rechaza el plan).
    """
    if not re.search(r"\(\s*=\s*\(\s*total-cost\s*\)", text, re.IGNORECASE):
        text = re.sub(
            r"\(\s*:init\b", "(:init\n    (= (total-cost) 0)", text, count=1, flags=re.IGNORECASE
        )
    if not re.search(r":metric", text, re.IGNORECASE):
        closing = text.rstrip().rfind(")")
        text = text[:closing] + "  (:metric minimize (total-cost))\n" + text[closing:]
    return text


def write_problem(
    name: str,
    domain: str,
    objects: dict[str, list[str]],
    init: list[str],
    goal: list[str],
    *,
    metric: str | None = None,
    comment: str | None = None,
) -> str:
    """Escribe un problema PDDL.

    Args:
        name: nombre del problema.
        domain: nombre del dominio.
        objects: objetos por tipo (``""`` para los objetos sin tipo).
        init: hechos y valores iniciales, ya escritos.
        goal: átomos del objetivo, ya escritos (se unen con ``and``).
        metric: la métrica sin ``(:metric ...)``, por ejemplo ``"minimize (total-time)"``.
        comment: comentario de cabecera.
    """
    lines: list[str] = []
    if comment:
        lines.extend(f"; {line}" for line in comment.splitlines())
    lines += [f"(define (problem {name})", f"  (:domain {domain})"]
    if objects:
        lines.append("  (:objects")
        for type_, names in objects.items():
            if names:
                suffix = f" - {type_}" if type_ else ""
                lines.append(f"    {' '.join(names)}{suffix}")
        lines.append("  )")
    lines.append("  (:init")
    lines.extend(f"    {fact}" for fact in init)
    lines.append("  )")
    if len(goal) == 1:
        lines.append(f"  (:goal {goal[0]})")
    else:
        lines.append("  (:goal (and")
        lines.extend(f"    {atom}" for atom in goal)
        lines.append("  ))")
    if metric:
        lines.append(f"  (:metric {metric})")
    lines.append(")")
    return "\n".join(lines) + "\n"


def number(value: float) -> str:
    """Un número para PDDL: sin decimales si es entero."""
    return str(int(value)) if float(value).is_integer() else f"{value:g}"
