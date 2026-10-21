"""Datasets: selecciones de problemas del catálogo para hacer pruebas.

Un dataset se define en un fichero TOML (en ``datasets/`` o en cualquier otra ruta) con
grupos explícitos, selecciones por filtros o ambas cosas::

    description = "Problemas para probar un planificador"
    description-en = "Problems to test a planner"   # opcional: la descripción en inglés

    [[group]]                     # un grupo explícito
    name = "strips/blocksworld"
    collection = "ipc-2000/blocks-strips-untyped"
    problems = ["p01", "p02"]     # opcional: todos si no se dice

    [[select]]                    # una selección: cada colección elegida es un grupo
    types = ["temporal"]          # tipos que tienen que tener los problemas (todos)
    exclude-types = ["pddlplus"]  # tipos que no pueden tener
    max-kb = 50
    per-collection = 3
    order = "random"              # "first" (por defecto), "random" o "smallest"
    seed = 1

Filtros de una selección (todos opcionales):

* ``collections`` / ``exclude-collections``: identificadores, con comodines
  (``ipc-2011/*``);
* ``types`` / ``exclude-types``: tipos (ver ``pddldomains types``); con ``types`` se exigen
  todos;
* ``requirements`` / ``exclude-requirements``: requisitos usados (``:durative-actions``);
* ``levels``: niveles de versión de PDDL admitidos, por número o nombre (``3``,
  ``"PDDL 2.1"``…; ver ``pddldomains levels``); ``min-level`` y ``max-level``: un rango de
  niveles. ``max-level = 3`` es lo que tiene que resolver un planificador que llega a PDDL
  2.1;
* ``problems``: nombres de problema, con comodines (``p0*``);
* ``min-objects``, ``max-objects``, ``max-kb``: tamaño de cada problema;
* ``with-plan``: solo problemas con plan de referencia;
* ``per-collection``: cuántos problemas como mucho de cada colección, en el orden ``order``
  (``seed`` fija el orden aleatorio);
* ``group``: plantilla del nombre del grupo, con ``{origin}``, ``{name}``, ``{id}`` y
  ``{level}`` (el nivel de la colección); por defecto, ``{id}``.

Los tipos, requisitos y niveles se miran en cada problema (con su dominio), así que una
selección puede quedarse solo con los problemas de una colección que usan, por ejemplo,
preferencias.
"""

import csv
import fnmatch
import io
import json
import random
import shutil
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pddldomains.analysis import Analyzer, TaskAnalysis
from pddldomains.catalog import ROOT, Catalog, CatalogError, Task, natural_key
from pddldomains.features import LEVELS, parse_level
from pddldomains.i18n import _, localized

#: Directorio de las definiciones de datasets del repositorio.
DATASETS_DIR = ROOT / "datasets"

_ORDERS = ("first", "random", "smallest")
_SELECT_KEYS = {
    "collections",
    "exclude-collections",
    "types",
    "exclude-types",
    "requirements",
    "exclude-requirements",
    "levels",
    "min-level",
    "max-level",
    "problems",
    "min-objects",
    "max-objects",
    "max-kb",
    "with-plan",
    "per-collection",
    "order",
    "seed",
    "group",
}
_GROUP_KEYS = {"name", "collection", "problems"}


class DatasetError(Exception):
    """Una definición de dataset mal escrita o imposible de exportar."""


@dataclass(frozen=True)
class Entry:
    """Un problema de un dataset.

    Attributes:
        group: grupo (el directorio donde va al exportar).
        task: el problema del catálogo.
        analysis: su análisis (tamaño, tipos…).
    """

    group: str
    task: Task
    analysis: TaskAnalysis

    def to_dict(self, *, relative_to: Path | None = None) -> dict[str, Any]:
        """El problema como diccionario, para el JSON y el CSV."""

        def show(path: Path | None) -> str | None:
            if path is None:
                return None
            if relative_to is not None and path.is_relative_to(relative_to):
                return path.relative_to(relative_to).as_posix()
            return str(path)

        return {
            "group": self.group,
            "collection": self.task.collection,
            "problem": self.task.name,
            "domain_file": show(self.task.domain),
            "problem_file": show(self.task.problem),
            "plan_file": show(self.task.plan),
            "tags": self.analysis.tags,
            "requirements": self.analysis.used,
            "size": self.analysis.size,
            "objects": self.analysis.objects,
            "init": self.analysis.init,
            "goals": self.analysis.goals,
        }


@dataclass
class Dataset:
    """Un dataset: problemas agrupados."""

    name: str
    description: str = ""
    entries: list[Entry] = field(default_factory=list)

    def __iter__(self) -> Iterator[Task]:
        return (entry.task for entry in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def groups(self) -> dict[str, list[Entry]]:
        """Los problemas por grupo, en orden."""
        result: dict[str, list[Entry]] = {}
        for entry in self.entries:
            result.setdefault(entry.group, []).append(entry)
        return result


def find_definition(name: str) -> Path:
    """La ruta de una definición: un fichero o un nombre de ``datasets/`` (sin ``.toml``)."""
    path = Path(name)
    if path.suffix == ".toml" and path.exists():
        return path
    candidate = DATASETS_DIR / f"{name}.toml"
    if candidate.exists():
        return candidate
    available = ", ".join(sorted(p.stem for p in DATASETS_DIR.glob("*.toml")))
    raise DatasetError(
        _(
            "no hay ningún dataset '{name}' (disponibles: {available})",
            name=name,
            available=available,
        )
    )


def load_definition(path: Path) -> dict[str, Any]:
    """Lee y comprueba una definición."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise DatasetError(f"{path}: {error}") from error
    unknown = set(data) - {"description", "description-en", "group", "select"}
    if unknown:
        raise DatasetError(
            _("{where}: claves desconocidas {keys}", where=path, keys=sorted(unknown))
        )
    for group in data.get("group", []):
        _check_keys(group, _GROUP_KEYS, f"{path}: [[group]]")
        if "name" not in group or "collection" not in group:
            raise DatasetError(
                _("{where}: cada [[group]] necesita 'name' y 'collection'", where=path)
            )
    for select in data.get("select", []):
        _check_selection(select, f"{path}: [[select]]")
    if not data.get("group") and not data.get("select"):
        raise DatasetError(_("{where}: no hay ningún [[group]] ni [[select]]", where=path))
    return data


def _check_keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise DatasetError(
            _("{where}: claves desconocidas {keys}", where=where, keys=sorted(unknown))
        )


def _check_selection(select: dict[str, Any], where: str) -> None:
    _check_keys(select, _SELECT_KEYS, where)
    order = select.get("order", "first")
    if order not in _ORDERS:
        raise DatasetError(
            _("{where}: 'order' tiene que ser uno de {values}", where=where, values=list(_ORDERS))
        )
    _level_filters(select, where)


def _level_filters(select: dict[str, Any], where: str) -> tuple[set[int] | None, int, int]:
    """Los filtros de nivel de una selección: niveles admitidos (o ``None``), mínimo y máximo."""
    try:
        allowed = {parse_level(v).number for v in select["levels"]} if "levels" in select else None
        low = parse_level(select["min-level"]).number if "min-level" in select else 1
        high = parse_level(select["max-level"]).number if "max-level" in select else len(LEVELS)
    except ValueError as error:
        raise DatasetError(f"{where}: {error}") from error
    return allowed, low, high


def load_dataset(name: str, catalog: Catalog | None = None) -> Dataset:
    """Construye un dataset a partir del nombre o la ruta de su definición."""
    path = find_definition(name)
    return build_dataset(load_definition(path), catalog, name=path.stem)


def select(catalog: Catalog | None = None, **filters: Any) -> Dataset:
    """Un dataset con una selección por filtros, con los nombres de ``[[select]]`` escritos
    con guiones bajos: ``select(types=["temporal"], per_collection=2, max_kb=50)``."""
    selection = {key.replace("_", "-"): value for key, value in filters.items()}
    return build_dataset({"select": [selection]}, catalog, name="seleccion")


def build_dataset(
    definition: dict[str, Any], catalog: Catalog | None = None, *, name: str = ""
) -> Dataset:
    """Construye un dataset a partir de una definición ya leída."""
    catalog = catalog or Catalog()
    analyzer = Analyzer(catalog)
    dataset = Dataset(name, " ".join(localized(definition, "description").split()))
    try:
        for group in definition.get("group", []):
            collection = catalog.find(group["collection"])
            analysis = analyzer.analyze(collection)
            names = group.get("problems")
            tasks = collection.tasks if names is None else [collection.task(n) for n in names]
            for task in tasks:
                dataset.entries.append(Entry(group["name"], task, analysis.task(task.name)))
        for select in definition.get("select", []):
            _check_selection(select, _("selección"))
            dataset.entries.extend(select_entries(catalog, analyzer, select))
    finally:
        analyzer.save()
    seen: set[tuple[str, str]] = set()
    for entry in dataset.entries:
        key = (entry.group, entry.task.name)
        if key in seen:
            raise DatasetError(
                _(
                    "el problema '{name}' está dos veces en el grupo '{group}'",
                    name=entry.task.name,
                    group=entry.group,
                )
            )
        seen.add(key)
    return dataset


def _matches(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def select_entries(catalog: Catalog, analyzer: Analyzer, select: dict[str, Any]) -> list[Entry]:
    """Los problemas que cumplen los filtros de una selección."""
    entries: list[Entry] = []
    template = select.get("group", "{id}")
    levels = _level_filters(select, _("selección"))
    for collection in catalog:
        if "collections" in select and not _matches(collection.id, select["collections"]):
            continue
        if _matches(collection.id, select.get("exclude-collections", [])):
            continue
        analysis = analyzer.analyze(collection)
        candidates = [
            (task, analysis.task(task.name))
            for task in collection.tasks
            if _accepts(task, analysis.task(task.name), select, levels)
        ]
        order = select.get("order", "first")
        if order == "random":
            rng = random.Random(f"{select.get('seed', 0)}:{collection.id}")
            rng.shuffle(candidates)
        elif order == "smallest":
            candidates.sort(key=lambda pair: (pair[1].size, natural_key(pair[0].name)))
        if "per-collection" in select:
            candidates = candidates[: select["per-collection"]]
        if order == "random":  # el orden aleatorio solo elige: el dataset va en orden natural
            candidates.sort(key=lambda pair: natural_key(pair[0].name))
        group = template.format(
            origin=collection.origin, name=collection.name, id=collection.id, level=analysis.level
        )
        entries.extend(Entry(group, task, task_analysis) for task, task_analysis in candidates)
    return entries


def _accepts(
    task: Task,
    analysis: TaskAnalysis,
    select: dict[str, Any],
    levels: tuple[set[int] | None, int, int],
) -> bool:
    if analysis.error:
        return False
    tags = set(analysis.tags)
    used = set(analysis.used)
    allowed_levels, min_level, max_level = levels
    checks = [
        allowed_levels is None or analysis.level in allowed_levels,
        min_level <= analysis.level <= max_level,
        set(select.get("types", [])) <= tags,
        not set(select.get("exclude-types", [])) & tags,
        set(select.get("requirements", [])) <= used,
        not set(select.get("exclude-requirements", [])) & used,
        "problems" not in select or _matches(task.name, select["problems"]),
        analysis.objects >= select.get("min-objects", 0),
        analysis.objects <= select.get("max-objects", analysis.objects),
        analysis.size <= select.get("max-kb", analysis.size / 1024) * 1024,
        not select.get("with-plan") or task.plan is not None,
    ]
    return all(checks)


# --- Salida ------------------------------------------------------------------------------


def to_lines(dataset: Dataset, *, relative_to: Path | None = None) -> str:
    """Una línea por problema: ``<dominio> <problema>``."""
    lines = []
    for entry in dataset.entries:
        data = entry.to_dict(relative_to=relative_to)
        lines.append(f"{data['domain_file']} {data['problem_file']}")
    return "\n".join(lines) + ("\n" if lines else "")


def to_json(dataset: Dataset, *, relative_to: Path | None = None) -> str:
    """El dataset en JSON: nombre, descripción y problemas."""
    data = {
        "name": dataset.name,
        "description": dataset.description,
        "tasks": [entry.to_dict(relative_to=relative_to) for entry in dataset.entries],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def to_csv(dataset: Dataset, *, relative_to: Path | None = None) -> str:
    """El dataset en CSV, una fila por problema."""
    output = io.StringIO()
    columns = [
        "group",
        "collection",
        "problem",
        "domain_file",
        "problem_file",
        "plan_file",
        "tags",
        "requirements",
        "size",
        "objects",
        "init",
        "goals",
    ]
    writer = csv.DictWriter(output, columns, lineterminator="\n")
    writer.writeheader()
    for entry in dataset.entries:
        row = entry.to_dict(relative_to=relative_to)
        row["tags"] = " ".join(row["tags"])
        row["requirements"] = " ".join(row["requirements"])
        writer.writerow(row)
    return output.getvalue()


def export(dataset: Dataset, destination: Path, *, link: bool = False, force: bool = False) -> int:
    """Copia el dataset a ``destination/<grupo>/`` (dominio, problemas y planes).

    Cada grupo queda con el formato del catálogo: ``domain.pddl`` (o ``domain-pNN.pddl``) y
    ``pNN.pddl``. Con ``link`` se crean enlaces simbólicos en lugar de copias. Se escribe
    además ``dataset.json`` con la lista de problemas (rutas relativas al destino).
    Devuelve el número de ficheros escritos.
    """
    if destination.exists() and any(destination.iterdir()) and not force:
        raise DatasetError(
            _("{path} no está vacío (use --force para sobrescribir)", path=destination)
        )
    written = 0
    sources: dict[Path, Path] = {}
    for group, entries in dataset.groups().items():
        directory = destination / group
        collections = {entry.task.collection for entry in entries}
        if len(collections) > 1:
            names = ", ".join(sorted(collections))
            raise DatasetError(
                _("el grupo '{group}' mezcla colecciones ({names})", group=group, names=names)
            )
        for entry in entries:
            task = entry.task
            files = [
                (task.domain, directory / task.domain.name),
                (task.problem, directory / task.problem.name),
            ]
            if task.plan is not None:
                files.append((task.plan, directory / task.plan.name))
            for source, target in files:
                if target in sources:
                    if sources[target] != source:
                        raise DatasetError(
                            _("{path}: dos ficheros distintos con el mismo destino", path=target)
                        )
                    continue
                sources[target] = source
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() or target.is_symlink():
                    target.unlink()
                if link:
                    target.symlink_to(source)
                else:
                    shutil.copy2(source, target)
                written += 1
    manifest = Dataset(dataset.name, dataset.description, [])
    manifest_entries = [
        {
            **entry.to_dict(),
            "domain_file": f"{entry.group}/{entry.task.domain.name}",
            "problem_file": f"{entry.group}/{entry.task.problem.name}",
            "plan_file": f"{entry.group}/{entry.task.plan.name}" if entry.task.plan else None,
        }
        for entry in dataset.entries
    ]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "dataset.json").write_text(
        json.dumps(
            {"name": manifest.name, "description": manifest.description, "tasks": manifest_entries},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return written


def selection_from_options(options: dict[str, Any]) -> dict[str, Any]:
    """Una selección a partir de opciones de la línea de comandos (sin las vacías)."""
    selection = {key: value for key, value in options.items() if value not in (None, [], False)}
    try:
        _check_selection(selection, _("opciones"))
    except DatasetError as error:
        raise CatalogError(str(error)) from error
    return selection
