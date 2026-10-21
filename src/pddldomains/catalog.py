"""El catálogo: ``dominios/<origen>/<colección>/``.

Cada colección es un directorio con:

* ``domain.pddl``, o un dominio por problema (``domain-<problema>.pddl``, como openstacks y
  parc-printer en la IPC 2011);
* los problemas: el resto de ficheros ``.pddl`` (normalmente ``pNN.pddl``);
* opcionalmente, planes de referencia ``<problema>.plan``;
* ``info.toml``, la ficha: origen, autores, erratas corregidas… (ver ``docs/es/catalogo.md``).

El identificador de una colección es ``<origen>/<colección>``, por ejemplo
``ipc-2006/trucks-time-constraints``. En la línea de comandos basta con la parte final si
no es ambigua (``trucks-time-constraints``).

El catálogo es el directorio ``dominios/`` del repositorio, salvo que la variable de entorno
``PDDL_DOMINIOS`` diga otra cosa.
"""

import os
import re
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from pddldomains.i18n import _

#: Raíz del repositorio.
ROOT = Path(__file__).resolve().parents[2]
#: Variable de entorno con otro directorio de catálogo.
ENV_VAR = "PDDL_DOMINIOS"
#: Nombre de la ficha de cada colección.
INFO_FILE = "info.toml"


def default_catalog_dir() -> Path:
    """El directorio del catálogo: ``$PDDL_DOMINIOS`` o ``dominios/`` del repositorio."""
    return Path(os.environ.get(ENV_VAR, ROOT / "dominios"))


class CatalogError(Exception):
    """Un identificador que no existe o es ambiguo, o una ficha mal escrita."""


def natural_key(text: str) -> list[Any]:
    """Clave de orden natural: ``p2`` va antes que ``p10``."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text)]


@dataclass(frozen=True)
class Task:
    """Un problema con su dominio.

    Attributes:
        collection: identificador de la colección.
        name: nombre del problema (el fichero sin ``.pddl``: ``p01``).
        domain: fichero del dominio.
        problem: fichero del problema.
        plan: plan de referencia, si lo hay.
    """

    collection: str
    name: str
    domain: Path
    problem: Path
    plan: Path | None = None

    @property
    def id(self) -> str:
        """``<colección>/<problema>``."""
        return f"{self.collection}/{self.name}"


@dataclass
class Collection:
    """Una colección del catálogo: un dominio y sus problemas."""

    id: str
    path: Path
    info: dict[str, Any] = field(default_factory=dict)
    tasks: list[Task] = field(default_factory=list)

    @property
    def origin(self) -> str:
        """El origen (``ipc-2006``…): la primera parte del identificador."""
        return self.id.split("/", 1)[0]

    @property
    def name(self) -> str:
        """El nombre de la colección: la segunda parte del identificador."""
        return self.id.split("/", 1)[1]

    def domain_files(self) -> list[Path]:
        """Los ficheros de dominio, sin repetir."""
        return sorted({task.domain for task in self.tasks}, key=lambda p: natural_key(p.name)) or [
            self.path / "domain.pddl"
        ]

    def task(self, name: str) -> Task:
        """El problema ``name`` (``p01`` o ``p01.pddl``)."""
        name = name.removesuffix(".pddl")
        for task in self.tasks:
            if task.name == name:
                return task
        raise CatalogError(
            _(
                "la colección '{collection}' no tiene el problema '{name}'",
                collection=self.id,
                name=name,
            )
        )


def is_domain_file(path: Path) -> bool:
    """Si un ``.pddl`` es un dominio por su nombre (``domain.pddl``, ``domain-p01.pddl``)."""
    return path.name == "domain.pddl" or path.name.startswith("domain-")


def read_collection(path: Path, collection_id: str) -> Collection:
    """Lee una colección de un directorio."""
    info: dict[str, Any] = {}
    info_path = path / INFO_FILE
    if info_path.exists():
        try:
            info = tomllib.loads(info_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            raise CatalogError(f"{info_path}: {error}") from error
    shared = path / "domain.pddl"
    tasks = []
    problems = sorted(
        (p for p in path.glob("*.pddl") if not is_domain_file(p)), key=lambda p: natural_key(p.name)
    )
    for problem in problems:
        own = path / f"domain-{problem.stem}.pddl"
        plan = problem.with_suffix(".plan")
        tasks.append(
            Task(
                collection_id,
                problem.stem,
                own if own.exists() else shared,
                problem,
                plan if plan.exists() else None,
            )
        )
    return Collection(collection_id, path, info, tasks)


class Catalog:
    """Las colecciones de un directorio de catálogo."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_catalog_dir()).resolve()
        if not self.root.is_dir():
            raise CatalogError(_("no existe el directorio del catálogo: {path}", path=self.root))

    @cached_property
    def collections(self) -> dict[str, Collection]:
        """Las colecciones por identificador, en orden."""
        result = {}
        for origin in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for path in sorted((p for p in origin.iterdir() if p.is_dir()), key=lambda p: p.name):
                if any(is_domain_file(p) for p in path.glob("*.pddl")):
                    collection_id = f"{origin.name}/{path.name}"
                    result[collection_id] = read_collection(path, collection_id)
        return result

    def __iter__(self) -> Iterator[Collection]:
        return iter(self.collections.values())

    def __len__(self) -> int:
        return len(self.collections)

    def find(self, key: str) -> Collection:
        """La colección ``key``: su identificador o, si no es ambigua, su parte final."""
        key = key.strip("/")
        if key in self.collections:
            return self.collections[key]
        matches = [c for c in self.collections.values() if c.name == key or c.id.endswith(key)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise CatalogError(
                _("no hay ninguna colección '{key}' (ver 'pddldomains list')", key=key)
            )
        names = ", ".join(c.id for c in matches)
        raise CatalogError(_("'{key}' es ambiguo: {names}", key=key, names=names))

    def find_task(self, key: str) -> Task:
        """Un problema: ``<colección>/<problema>`` (con la colección como en :meth:`find`)."""
        collection, _slash, name = key.strip("/").rpartition("/")
        if not collection:
            raise CatalogError(_("se esperaba '<colección>/<problema>': '{key}'", key=key))
        return self.find(collection).task(name)
