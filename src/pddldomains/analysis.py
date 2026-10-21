"""Análisis de las colecciones: requisitos usados, tipos y tamaño de cada problema.

Analizar todo el catálogo lleva unos segundos, así que el resultado se guarda en
``.cache/analisis.json`` (en la raíz del repositorio) por colección, junto con el tamaño y
la fecha de sus ficheros: si alguno cambia, la colección se vuelve a analizar.
"""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pddldomains.catalog import ROOT, Catalog, Collection, Task
from pddldomains.features import (
    RequirementUse,
    classify,
    domain_uses,
    level_of,
    normalize_used,
    problem_uses,
    undeclared,
    used_requirements,
)
from pddldomains.i18n import _, language
from pddldomains.pddl import (
    Domain,
    PDDLStructureError,
    Problem,
    read_domain,
    read_problem,
    read_text,
)
from pddldomains.sexpr import PDDLSyntaxError, SExpr, SList

#: Versión del análisis: al cambiarla se invalida la caché.
ANALYSIS_VERSION = 2
#: Fichero de la caché.
CACHE_FILE = ROOT / ".cache" / "analisis.json"

_CONNECTIVES = frozenset({"and", "or", "not", "imply", "exists", "forall", "preference"})


@dataclass
class TaskAnalysis:
    """Lo que se sabe de un problema.

    Attributes:
        name: nombre del problema.
        size: tamaño del fichero en bytes.
        objects: objetos (los del problema más las constantes del dominio).
        init: hechos y valores iniciales.
        goals: átomos del objetivo.
        used: requisitos usados por el dominio y el problema.
        tags: tipos (ver :data:`pddldomains.features.TAGS`).
        level: nivel de versión de PDDL (ver :data:`pddldomains.features.LEVELS`).
        undeclared: requisitos usados sin declarar.
        error: error de lectura, si lo hubo.
    """

    name: str
    size: int
    objects: int = 0
    init: int = 0
    goals: int = 0
    used: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    level: int = 1
    undeclared: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class CollectionAnalysis:
    """Lo que se sabe de una colección (la unión de sus problemas)."""

    id: str
    domain_name: str = ""
    declared: list[str] = field(default_factory=list)
    used: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    #: Nivel de versión de PDDL (el más alto de sus problemas).
    level: int = 1
    operators: int = 0
    predicates: int = 0
    functions: int = 0
    tasks: list[TaskAnalysis] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def task(self, name: str) -> TaskAnalysis:
        """El análisis del problema ``name``."""
        return next(t for t in self.tasks if t.name == name)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "CollectionAnalysis":
        """Reconstruye un análisis guardado en la caché."""
        tasks = [TaskAnalysis(**t) for t in data.pop("tasks")]
        return CollectionAnalysis(**data, tasks=tasks)


def count_atoms(node: SExpr | None) -> int:
    """Átomos de una fórmula (las hojas que no son conectivas ni cuantificadores)."""
    if not isinstance(node, SList) or not node:
        return 0
    head = node[0]
    if head in ("exists", "forall") and len(node) == 3:
        return count_atoms(node[2])
    if head == "preference":
        return count_atoms(node[-1])
    if head in _CONNECTIVES:
        return sum(count_atoms(child) for child in node[1:])
    return 1


def analyze_collection(collection: Collection) -> CollectionAnalysis:
    """Analiza una colección leyendo todos sus ficheros."""
    result = CollectionAnalysis(collection.id)
    domains: dict[Path, Domain | str] = {}
    for path in collection.domain_files():
        try:
            domains[path] = read_domain(read_text(path))
        except (PDDLSyntaxError, PDDLStructureError, OSError) as error:
            domains[path] = str(error)
            result.errors.append(f"{path.name}: {error}")
    first = next((d for d in domains.values() if isinstance(d, Domain)), None)
    if first is not None:
        result.domain_name = first.name
        result.operators = len(first.operators)
        result.predicates = len(first.predicates)
        result.functions = len(first.functions)
    declared: set[str] = set()
    domain_used: dict[Path, list[RequirementUse]] = {}
    for path, domain in domains.items():
        if isinstance(domain, Domain):
            declared.update(domain.requirements)
            domain_used[path] = domain_uses(domain)
    used_all: set[str] = set()
    for path in domain_used:
        used_all |= used_requirements(domain_used[path])
    for task in collection.tasks:
        analysis = analyze_task(task, domains.get(task.domain), domain_used.get(task.domain, []))
        result.tasks.append(analysis)
        used_all.update(analysis.used)
        if analysis.error:
            result.errors.append(f"{task.problem.name}: {analysis.error}")
    used = normalize_used(used_all)
    result.declared = sorted(declared)
    result.used = sorted(used)
    result.tags = classify(used)
    result.level = level_of(used).number
    return result


def analyze_task(
    task: Task, domain: Domain | str | None, uses_of_domain: list[RequirementUse]
) -> TaskAnalysis:
    """Analiza un problema con su dominio ya leído."""
    size = task.problem.stat().st_size
    if not isinstance(domain, Domain):
        return TaskAnalysis(
            task.name, size, error=_("dominio no legible ({detail})", detail=domain)
        )
    try:
        problem: Problem = read_problem(read_text(task.problem))
    except (PDDLSyntaxError, PDDLStructureError, OSError) as error:
        return TaskAnalysis(task.name, size, error=str(error))
    uses = [*uses_of_domain, *problem_uses(problem, domain)]
    used = used_requirements(uses)
    missing = undeclared(uses, [*domain.requirements, *problem.requirements])
    return TaskAnalysis(
        task.name,
        size,
        objects=len(problem.objects) + len(domain.constants),
        init=len(problem.init or ()),
        goals=count_atoms(problem.goal),
        used=sorted(used),
        tags=classify(used),
        level=level_of(used).number,
        undeclared=sorted({u.requirement for u in missing}),
    )


def _signature(collection: Collection) -> list[list[Any]]:
    files = sorted({*collection.domain_files(), *(t.problem for t in collection.tasks)})
    result = []
    for path in files:
        stat = path.stat()
        result.append([path.name, stat.st_size, stat.st_mtime_ns])
    return result


class Analyzer:
    """Analiza las colecciones de un catálogo con la caché de ``.cache/analisis.json``."""

    def __init__(self, catalog: Catalog, cache_file: Path | None = CACHE_FILE) -> None:
        self.catalog = catalog
        self.cache_file = cache_file
        self._cache: dict[str, Any] = self._load()
        self._dirty = False

    def _load(self) -> dict[str, Any]:
        if self.cache_file is None or not self.cache_file.exists():
            return {}
        try:
            data = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if (
            data.get("version") != ANALYSIS_VERSION
            or data.get("root") != str(self.catalog.root)
            or data.get("language") != language()  # los errores guardados van en un idioma
        ):
            return {}
        entries: dict[str, Any] = data.get("collections", {})
        return entries

    def analyze(self, collection: Collection) -> CollectionAnalysis:
        """El análisis de una colección (de la caché si sus ficheros no han cambiado)."""
        signature = _signature(collection)
        cached = self._cache.get(collection.id)
        if cached and cached["signature"] == signature:
            return CollectionAnalysis.from_dict(dict(cached["analysis"]))
        analysis = analyze_collection(collection)
        self._cache[collection.id] = {"signature": signature, "analysis": asdict(analysis)}
        self._dirty = True
        return analysis

    def analyze_all(self) -> dict[str, CollectionAnalysis]:
        """El análisis de todas las colecciones; guarda la caché si ha cambiado."""
        result = {c.id: self.analyze(c) for c in self.catalog}
        self.save()
        return result

    def save(self) -> None:
        """Guarda la caché si hay análisis nuevos."""
        if not self._dirty or self.cache_file is None:
            return
        data = {
            "version": ANALYSIS_VERSION,
            "root": str(self.catalog.root),
            "language": language(),
            "collections": {k: v for k, v in self._cache.items() if k in self.catalog.collections},
        }
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_file.with_suffix(f".{os.getpid()}.tmp")
            temporary.write_text(json.dumps(data), encoding="utf-8")
            temporary.replace(self.cache_file)
        except OSError:
            pass  # Sin caché, el análisis se repite la próxima vez; no es un error.
        self._dirty = False
