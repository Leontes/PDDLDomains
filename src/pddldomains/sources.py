"""Los ficheros originales de cada colección: compararlos con el catálogo y traer más problemas.

La sección ``[origin]`` de la ficha (``info.toml``) dice de dónde sale una colección:
repositorio, commit, ruta y los patrones de los nombres de los ficheros, donde ``{n}`` es el
número del problema y ``{nn}``, el mismo con dos cifras::

    [origin]
    repository = "https://github.com/potassco/pddl-instances"
    commit = "cf19edf"
    path = "ipc-2006/domains/trucks-time-constraints"
    domain = "domain.pddl"
    problems = "instances/instance-{n}.pddl"

El problema ``pNN.pddl`` del catálogo es el ``n = NN`` del origen; si el patrón del dominio
lleva ``{n}``, cada problema tiene su dominio (``domain-pNN.pddl``).

Los repositorios se clonan sin contenido (``--filter=blob:none``) en ``tools/fuentes/`` y
cada fichero se lee con ``git show <commit>:<ruta>``, que solo descarga lo que hace falta.

Comparar el catálogo con el origen (:func:`compare`) dice qué ficheros se han corregido; cada
diferencia tiene que estar documentada en las erratas de la ficha (su lista ``files``, que
admite comodines como ``p*.pddl``).
"""

import difflib
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pddldomains.catalog import ROOT, CatalogError, Collection
from pddldomains.i18n import _

#: Directorio de los clones de los repositorios de origen.
SOURCES_DIR = ROOT / "tools" / "fuentes"


class SourceError(Exception):
    """No se puede leer el origen de una colección."""


def problem_number(name: str) -> int | None:
    """El número de un problema por su nombre (``p07`` → 7); ``None`` si no lo tiene."""
    match = re.fullmatch(r"p(\d+)", name)
    return int(match.group(1)) if match else None


@dataclass(frozen=True)
class Origin:
    """La sección ``[origin]`` de una ficha."""

    repository: str
    commit: str
    path: str
    domain: str
    problems: str
    plans: str | None = None
    instances: int | None = None

    @staticmethod
    def from_info(info: dict[str, Any]) -> "Origin | None":
        """El origen de una ficha, o ``None`` si no tiene repositorio (una colección propia)."""
        origin = info.get("origin", {})
        if "repository" not in origin:
            return None
        return Origin(
            origin["repository"],
            origin["commit"],
            origin["path"],
            origin["domain"],
            origin["problems"],
            origin.get("plans"),
            origin.get("instances"),
        )

    @property
    def per_problem_domain(self) -> bool:
        """Si cada problema tiene su propio dominio."""
        return "{n" in self.domain

    def file(self, pattern: str, number: int | None) -> str:
        """Ruta en el repositorio del fichero de ``pattern`` para el problema ``number``."""
        name = pattern.format(n=number, nn=f"{number:02d}") if number is not None else pattern
        return f"{self.path}/{name}" if self.path else name


def _repo_dir(url: str) -> Path:
    owner_repo = url.rstrip("/").removesuffix(".git").split("/")[-2:]
    return SOURCES_DIR / "__".join(owner_repo)


class SourceRepo:
    """Un repositorio de origen clonado sin contenido."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.dir = _repo_dir(url)

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", "-C", str(self.dir), *args], capture_output=True, check=check)

    def ensure(self, commit: str) -> None:
        """Clona el repositorio si hace falta y se asegura de tener el commit."""
        if not (self.dir / ".git").exists() and not (self.dir / "HEAD").exists():
            self.dir.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--filter=blob:none",
                    "--no-checkout",
                    self.url,
                    str(self.dir),
                ],
                capture_output=True,
            )
            if result.returncode != 0:
                raise SourceError(
                    _(
                        "no se ha podido clonar {url}: {detail}",
                        url=self.url,
                        detail=result.stderr.decode().strip(),
                    )
                )
        if self._git("cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
            self._git("fetch", "--quiet", "origin", check=False)
            if self._git("cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode != 0:
                raise SourceError(
                    _("{url} no tiene el commit {commit}", url=self.url, commit=commit)
                )

    def read(self, commit: str, path: str) -> bytes | None:
        """El contenido de ``path`` en ``commit``; ``None`` si no existe."""
        result = self._git("show", f"{commit}:{path}", check=False)
        return result.stdout if result.returncode == 0 else None

    def exists(self, commit: str, path: str) -> bool:
        """Si ``path`` existe en ``commit`` (sin descargar su contenido)."""
        return self._git("cat-file", "-e", f"{commit}:{path}", check=False).returncode == 0


def origin_of(collection: Collection) -> Origin:
    """El origen de una colección; error si es propia."""
    origin = Origin.from_info(collection.info)
    if origin is None:
        raise CatalogError(
            _("'{collection}' no tiene repositorio de origen en su ficha", collection=collection.id)
        )
    return origin


def _open(origin: Origin) -> SourceRepo:
    repo = SourceRepo(origin.repository)
    repo.ensure(origin.commit)
    return repo


@dataclass(frozen=True)
class FileComparison:
    """Un fichero del catálogo frente a su original.

    Attributes:
        name: nombre en el catálogo (``domain.pddl``, ``p03.pddl``…).
        status: ``"same"`` (igual), ``"changed"`` (corregido) o ``"missing"`` (sin original).
        documented: si la diferencia está en las erratas de la ficha.
        diff: diferencias (original → catálogo) en formato unificado.
    """

    name: str
    status: str
    documented: bool = True
    diff: str = ""


def documented_files(collection: Collection) -> list[str]:
    """Los patrones de los ficheros corregidos según las erratas de la ficha."""
    return [f for errata in collection.info.get("errata", []) for f in errata.get("files", [])]


def _origin_files(collection: Collection, origin: Origin) -> list[tuple[str, Path, str]]:
    """Cada fichero del catálogo con su ruta en el origen: (nombre, ruta local, ruta de origen)."""
    files = []
    if not origin.per_problem_domain:
        files.append(
            ("domain.pddl", collection.path / "domain.pddl", origin.file(origin.domain, None))
        )
    for task in collection.tasks:
        number = problem_number(task.name)
        if number is None:
            continue
        if origin.per_problem_domain:
            files.append((task.domain.name, task.domain, origin.file(origin.domain, number)))
        files.append((task.problem.name, task.problem, origin.file(origin.problems, number)))
        if origin.plans and task.plan is not None:
            files.append((task.plan.name, task.plan, origin.file(origin.plans, number)))
    return files


def compare(collection: Collection) -> list[FileComparison]:
    """Compara los ficheros de una colección con sus originales."""
    origin = origin_of(collection)
    repo = _open(origin)
    patterns = documented_files(collection)
    result = []
    for name, local, remote in _origin_files(collection, origin):
        original = repo.read(origin.commit, remote)
        if original is None:
            result.append(FileComparison(name, "missing", False))
            continue
        current = local.read_bytes()
        if current == original:
            result.append(FileComparison(name, "same"))
            continue
        documented = any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
        diff = "".join(
            difflib.unified_diff(
                original.decode("utf-8", errors="replace").splitlines(keepends=True),
                current.decode("utf-8", errors="replace").splitlines(keepends=True),
                f"original/{remote}",
                f"catálogo/{collection.id}/{name}",
            )
        )
        result.append(FileComparison(name, "changed", documented, diff))
    return result


def available_problems(collection: Collection) -> list[int]:
    """Los números de los problemas del origen (hasta ``instances`` o el primero que falte)."""
    origin = origin_of(collection)
    repo = _open(origin)
    limit = origin.instances or 999
    numbers = []
    for number in range(1, limit + 1):
        if not repo.exists(origin.commit, origin.file(origin.problems, number)):
            if origin.instances is None:
                break
            continue
        numbers.append(number)
    return numbers


def fetch_problems(
    collection: Collection, numbers: list[int], *, overwrite: bool = False
) -> list[Path]:
    """Copia del origen los problemas ``numbers`` (con su dominio y su plan, si los hay).

    Los ficheros se copian sin modificar: si necesitan erratas, hay que corregirlas y
    documentarlas a mano (``pddldomains lint`` las encuentra). Devuelve los ficheros escritos.
    """
    origin = origin_of(collection)
    repo = _open(origin)
    written = []

    def copy(remote: str, local: Path, required: bool = True) -> None:
        if local.exists() and not overwrite:
            return
        content = repo.read(origin.commit, remote)
        if content is None:
            if required:
                raise SourceError(
                    _(
                        "no existe {path} en {repository}@{commit}",
                        path=remote,
                        repository=origin.repository,
                        commit=origin.commit,
                    )
                )
            return
        local.write_bytes(content)
        written.append(local)

    if not origin.per_problem_domain:
        copy(origin.file(origin.domain, None), collection.path / "domain.pddl")
    for number in numbers:
        name = f"p{number:02d}"
        if origin.per_problem_domain:
            copy(origin.file(origin.domain, number), collection.path / f"domain-{name}.pddl")
        copy(origin.file(origin.problems, number), collection.path / f"{name}.pddl")
        if origin.plans:
            copy(
                origin.file(origin.plans, number), collection.path / f"{name}.plan", required=False
            )
    return written
