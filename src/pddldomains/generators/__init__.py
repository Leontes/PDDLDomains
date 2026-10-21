"""Generadores de problemas aleatorios para las colecciones del catálogo.

* :mod:`~pddldomains.generators.own`: propios, para las colecciones sin generador público
  que encaje (numéricas de la IPC 2023, SMTPlan, greenhouse);
* :mod:`~pddldomains.generators.external`: envolturas de pddl-generators y de los
  generadores de la IPC 2023 (``scripts/build_generators.sh``);
* :mod:`~pddldomains.generators.parking`: el de parking de pddl-generators, portado de Perl
  a Python;
* :mod:`~pddldomains.generators.walk`: genérico por paseo aleatorio, para cualquier
  colección clásica.
"""

from pddldomains.catalog import Catalog, CatalogError
from pddldomains.generators.base import GeneratedProblem, Generator, GeneratorError, Param
from pddldomains.generators.external import EXTERNAL_GENERATORS
from pddldomains.generators.own import OWN_GENERATORS
from pddldomains.generators.parking import ParkingGenerator
from pddldomains.generators.walk import RandomWalkGenerator
from pddldomains.i18n import _

#: Todos los generadores por nombre.
GENERATORS: dict[str, Generator] = {
    g.name: g
    for g in (*OWN_GENERATORS, ParkingGenerator(), *EXTERNAL_GENERATORS, RandomWalkGenerator())
}


def find_generator(key: str, catalog: Catalog | None = None) -> Generator:
    """Un generador por su nombre o por la colección para la que genera."""
    if key in GENERATORS:
        return GENERATORS[key]
    try:
        collection = (catalog or Catalog()).find(key)
    except CatalogError as error:
        raise GeneratorError(
            _("no hay ningún generador '{key}' (ver 'pddldomains generate --list')", key=key)
        ) from error
    matches = [g for g in GENERATORS.values() if g.collection == collection.id]
    if not matches:
        raise GeneratorError(
            _(
                "'{collection}' no tiene generador propio; si es clásica, use "
                "'pddldomains generate random-walk -p collection={collection}'",
                collection=collection.id,
            )
        )
    return matches[0]


__all__ = [
    "GENERATORS",
    "GeneratedProblem",
    "Generator",
    "GeneratorError",
    "Param",
    "find_generator",
]
