"""Catálogo de dominios PDDL con herramientas para clasificarlos, crear datasets, revisarlos
y generar problemas.

Uso desde Python (por ejemplo, para parametrizar los tests de un planificador)::

    from pddldomains import load_dataset, select

    for task in load_dataset("smoke-test"):
        print(task.domain, task.problem)

    # o una selección por filtros, como los de [[select]] (con guiones bajos)
    tasks = list(select(types=["temporal"], per_collection=2))
"""

__version__ = "0.1.0"

from pddldomains.catalog import Catalog, Collection, Task  # noqa: E402
from pddldomains.datasets import Dataset, load_dataset, select  # noqa: E402

__all__ = ["Catalog", "Collection", "Dataset", "Task", "__version__", "load_dataset", "select"]
